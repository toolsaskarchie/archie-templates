"""
VPC Production Template

Creates an enterprise-grade VPC with 3 availability zones and 3-tier architecture.
Includes public (DMZ), private (application), and isolated (database) subnets.
Follows AWS Well-Architected Framework for high availability and security.

REFACTORED TO USE FACTORY PATTERN - Pattern B (Pulumi as source of truth)
"""

from typing import Any, Dict, List, Optional
from pathlib import Path
import pulumi
import pulumi_aws as aws
import json

# Import Archie utils for consistent patterns
from provisioner.utils.aws import ResourceNamer
from provisioner.utils.aws.naming import get_cloudwatch_log_group_name
from provisioner.utils.cidr_calculator import calculate_subnet_cidrs
from provisioner.templates.base import template_registry, InfrastructureTemplate
from provisioner.templates.template_config import TemplateConfig
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory


@template_registry("aws-vpc-prod")
class VPCProdTemplate(InfrastructureTemplate):
    """
    VPC Production Template - Reference Architecture
    
    Features:
    - 3 Availability Zones for maximum high availability
    - 3-Tier Architecture: Public (DMZ), Private (App), Isolated (DB)
    - 9 Subnets total (3 per tier)
    - High Availability NAT: 3 NAT Gateways (one per AZ)
    - Zero-trust security: Public -> Private -> Isolated isolation
    - Integrated Flow Logs for audit and monitoring
    - Private Service Access: VPC Endpoints for S3 and DynamoDB
    """
    
    @staticmethod
    def _to_bool(val) -> bool:
        """Convert any value to bool. Handles: True, 1, '1', 'true', Decimal(1)."""
        if isinstance(val, bool): return val
        if isinstance(val, (int, float)): return val != 0
        if isinstance(val, str): return val.lower() in ('true', '1', 'yes')
        try: return int(val) != 0
        except (TypeError, ValueError): return bool(val)

    def __init__(self, name: str = None, config: Dict[str, Any] = None, aws: Dict[str, Any] = None, **kwargs):
        """Initialize VPC Prod template"""
        raw_config = config or aws or kwargs or {}
        
        if name is None:
            name = raw_config.get('project_name', 'vpc-prod')
        
        super().__init__(name, raw_config)
        
        # Load template configuration
        template_dir = Path(__file__).parent
        self.cfg = TemplateConfig(template_dir, raw_config)
        self.config = raw_config
        
        # Resource references
        self.vpc: Optional[aws.ec2.Vpc] = None
        self.igw: Optional[aws.ec2.InternetGateway] = None
        self.nat_gateways: List[aws.ec2.NatGateway] = []
        self.subnets = {}
        self.route_tables = {}
        self.security_groups = {}
        self.vpc_endpoints = {}
        self.flow_logs = None
    
    def create_infrastructure(self) -> Dict[str, Any]:
        """Deploy production VPC infrastructure using factory pattern"""
        return self.create()

    def create(self) -> Dict[str, Any]:
        """Deploy production VPC infrastructure"""

        # Get configuration values
        project_name = self.cfg.get('project_name', 'vpc-prod')
        region = self.cfg.get('region', 'us-east-1')
        
        # Initialize ResourceNamer for self-documenting names
        namer = ResourceNamer(
            project=project_name,
            environment="prod",
            region=region,
            template="vpc-prod"
        )
        
        # Generate random VPC CIDR if needed
        cidr_block = self.cfg.get('cidr_block', 'random')
        if not cidr_block or cidr_block == '10.0.0.0/16' or cidr_block == 'random':
            from provisioner.utils.aws.cidr_utils import generate_random_vpc_cidr
            cidr_block = generate_random_vpc_cidr()
        
        # Calculate subnet CIDRs (9 subnets: 3 per tier)
        from provisioner.utils.aws.cidr_utils import calculate_subnet_cidrs
        all_subnet_cidrs = calculate_subnet_cidrs(cidr_block, count=9, subnet_prefix=24)
        public_cidrs = all_subnet_cidrs[0:3]
        private_cidrs = all_subnet_cidrs[3:6]
        isolated_cidrs = all_subnet_cidrs[6:9]
        
        # 1. Create VPC
        vpc_name = self.cfg.get('vpc_name')
        vpc_resource_name = vpc_name or namer.vpc()
        raw_dns_support = self.config.get('enable_dns_support', self.config.get('parameters', {}).get('enable_dns_support', True))
        raw_dns_hostnames = self.config.get('enable_dns_hostnames', self.config.get('parameters', {}).get('enable_dns_hostnames', True))
        dns_support = self._to_bool(raw_dns_support)
        dns_hostnames = self._to_bool(raw_dns_hostnames)
        print(f"[VPC DEBUG] enable_dns_support: raw={raw_dns_support} ({type(raw_dns_support).__name__}) -> {dns_support} ({type(dns_support).__name__})")
        print(f"[VPC DEBUG] enable_dns_hostnames: raw={raw_dns_hostnames} ({type(raw_dns_hostnames).__name__}) -> {dns_hostnames} ({type(dns_hostnames).__name__})")
        self.vpc = factory.create(
            "aws:ec2:Vpc",
            vpc_resource_name,
            cidr_block=cidr_block,
            enable_dns_support=dns_support,
            enable_dns_hostnames=dns_hostnames,
            instance_tenancy=self.cfg.get('instance_tenancy', 'default'),
            tags={
                "Name": vpc_resource_name,
                "Project": project_name,
                "Environment": "prod",
                "ManagedBy": "Archie"
            }
        )
        vpc_id = self.vpc.id
        
        # 2. Internet Gateway
        igw_name = namer.internet_gateway()
        self.igw = factory.create(
            "aws:ec2:InternetGateway",
            igw_name,
            vpc_id=vpc_id,
            tags={
                "Name": igw_name,
                "Project": project_name,
                "Environment": "prod"
            }
        )
        igw_id = self.igw.id
        
        # Get region shortcode
        region_short = namer.region_short

        # Get AZ configuration (handle empty defaults)
        az_1 = self.cfg.get('az_1') or f'{region}a'
        az_2 = self.cfg.get('az_2') or f'{region}b'
        az_3 = self.cfg.get('az_3') or f'{region}c'
        az_list = [az_1, az_2, az_3]
        
        # Handle NAT configuration
        enable_nat_gateway = self.cfg.get('enable_nat_gateway', True)
        nat_gateway_count = self.cfg.get('nat_gateway_count', 3)
        
        # 3. Route Tables (Create ALL route tables BEFORE subnets for consistent ordering)
        # Public Route Table
        public_rt_name = namer.route_table("public")
        public_rt = factory.create(
            "aws:ec2:RouteTable",
            public_rt_name,
            vpc_id=vpc_id,
            tags={
                "Name": public_rt_name,
                "Project": project_name,
                "Environment": "prod",
                "Tier": "public"
            }
        )
        public_rt_id = public_rt.id
        
        # Private Route Tables (3x - one per AZ)
        private_rts = []
        for i in range(3):
            idx = i + 1
            az = az_list[i]
            priv_rt_name = namer.route_table("private", az)
            priv_rt = factory.create(
                "aws:ec2:RouteTable",
                priv_rt_name,
                vpc_id=vpc_id,
                tags={
                    "Name": priv_rt_name,
                    "Project": project_name,
                    "Environment": "prod",
                    "Tier": "private",
                    "AZ": az
                }
            )
            private_rts.append(priv_rt)
            self.route_tables[f"private-{idx}"] = priv_rt
        
        # Track route tables for VPC endpoints
        endpoint_rt_ids = [public_rt_id] + [rt.id for rt in private_rts]
        private_subnet_ids = []
        
        # 4. VPC Endpoints (Gateway) - Always created (free) - BEFORE Security Groups
        s3_name = namer.vpc_endpoint("s3", "gateway")
        self.vpc_endpoints['s3'] = factory.create(
            "aws:ec2:VpcEndpoint",
            s3_name,
            vpc_id=vpc_id,
            service_name=f"com.amazonaws.{region}.s3",
            vpc_endpoint_type="Gateway",
            route_table_ids=endpoint_rt_ids,
            tags={
                "Name": s3_name,
                "Project": project_name,
                "Environment": "prod"
            }
        )
        
        ddb_name = namer.vpc_endpoint("dynamodb", "gateway")
        self.vpc_endpoints['dynamodb'] = factory.create(
            "aws:ec2:VpcEndpoint",
            ddb_name,
            vpc_id=vpc_id,
            service_name=f"com.amazonaws.{region}.dynamodb",
            vpc_endpoint_type="Gateway",
            route_table_ids=endpoint_rt_ids,
            tags={
                "Name": ddb_name,
                "Project": project_name,
                "Environment": "prod"
            }
        )

        # 5. Security Groups (Expanded for UI visibility)
        # Web SG - HTTP/HTTPS access
        web_sg_name = namer.security_group('web', ports=[80, 443])
        self.security_groups['web'] = factory.create(
            "aws:ec2:SecurityGroup",
            web_sg_name,
            vpc_id=vpc_id,
            description="Security group for web tier - allows HTTP/HTTPS traffic",
            ingress=[
                {"protocol": "tcp", "from_port": 80, "to_port": 80, "cidr_blocks": ["0.0.0.0/0"]},
                {"protocol": "tcp", "from_port": 443, "to_port": 443, "cidr_blocks": ["0.0.0.0/0"]}
            ],
            egress=[{"protocol": "-1", "from_port": 0, "to_port": 0, "cidr_blocks": ["0.0.0.0/0"]}],
            tags={
                "Name": web_sg_name,
                "Project": project_name,
                "Environment": "prod",
                "Tier": "web",
                "ManagedBy": "Archie"
            }
        )
        
        # App SG - Application tier
        app_sg_name = namer.security_group('app')
        self.security_groups['app'] = factory.create(
            "aws:ec2:SecurityGroup",
            app_sg_name,
            vpc_id=vpc_id,
            description="Security group for application tier",
            egress=[{"protocol": "-1", "from_port": 0, "to_port": 0, "cidr_blocks": ["0.0.0.0/0"]}],
            tags={
                "Name": app_sg_name,
                "Project": project_name,
                "Environment": "prod",
                "Tier": "app",
                "ManagedBy": "Archie"
            }
        )
        
        # DB SG - Database tier
        db_sg_name = namer.security_group('db')
        self.security_groups['db'] = factory.create(
            "aws:ec2:SecurityGroup",
            db_sg_name,
            vpc_id=vpc_id,
            description="Security group for database tier",
            egress=[{"protocol": "-1", "from_port": 0, "to_port": 0, "cidr_blocks": ["0.0.0.0/0"]}],
            tags={
                "Name": db_sg_name,
                "Project": project_name,
                "Environment": "prod",
                "Tier": "db",
                "ManagedBy": "Archie"
            }
        )
        
        # Access SG - SSH/RDP access
        ssh_access_ip = self.cfg.get('ssh_access_ip', '')
        access_sg_name = namer.security_group('access', ports=[22, 3389] if ssh_access_ip else None)
        access_sg_ingress = []
        if ssh_access_ip:
            # Handle single IP (string) or list for backward compatibility
            allowed_ips = [ssh_access_ip] if isinstance(ssh_access_ip, str) else ssh_access_ip
            
            for ip in allowed_ips:
                if not ip: continue
                cidr_ip = ip if '/' in ip else f"{ip}/32"
                access_sg_ingress.append({"protocol": "tcp", "from_port": 22, "to_port": 22, "cidr_blocks": [cidr_ip], "description": f"SSH from {cidr_ip}"})
                access_sg_ingress.append({"protocol": "tcp", "from_port": 3389, "to_port": 3389, "cidr_blocks": [cidr_ip], "description": f"RDP from {cidr_ip}"})
        self.security_groups['access'] = factory.create(
            "aws:ec2:SecurityGroup",
            access_sg_name,
            vpc_id=vpc_id,
            description="Security group for SSH/RDP access",
            ingress=access_sg_ingress,
            egress=[{"protocol": "-1", "from_port": 0, "to_port": 0, "cidr_blocks": ["0.0.0.0/0"]}],
            tags={
                "Name": access_sg_name,
                "Project": project_name,
                "Environment": "prod",
                "Tier": "access",
                "ManagedBy": "Archie"
            }
        )
        
        # 6. Create 3 AZs worth of subnets
        # On upgrade (vpc_name injected from outputs), skip CIDR in subnet names
        # to match existing resource names from the original deploy
        is_upgrade = bool(vpc_name)
        for i in range(3):
            az = az_list[i]
            idx = i + 1

            # PUBLIC SUBNET
            pub_cidr = public_cidrs[i]
            pub_sub_name = namer.subnet("public", az) if is_upgrade else namer.subnet("public", az, cidr=pub_cidr)
            pub_subnet = factory.create(
                "aws:ec2:Subnet",
                pub_sub_name,
                vpc_id=vpc_id,
                cidr_block=pub_cidr,
                availability_zone=az,
                map_public_ip_on_launch=True,
                tags={
                    "Name": pub_sub_name,
                    "Project": project_name,
                    "Environment": "prod",
                    "Tier": "public",
                    "AZ": az
                }
            )
            self.subnets[f"public-{idx}"] = pub_subnet
            
            # PRIVATE SUBNET
            priv_cidr = private_cidrs[i]
            priv_sub_name = namer.subnet("private", az) if is_upgrade else namer.subnet("private", az, cidr=priv_cidr)
            priv_subnet = factory.create(
                "aws:ec2:Subnet",
                priv_sub_name,
                vpc_id=vpc_id,
                cidr_block=priv_cidr,
                availability_zone=az,
                map_public_ip_on_launch=False,
                tags={
                    "Name": priv_sub_name,
                    "Project": project_name,
                    "Environment": "prod",
                    "Tier": "private",
                    "AZ": az
                }
            )
            self.subnets[f"private-{idx}"] = priv_subnet
            private_subnet_ids.append(priv_subnet.id)
            
            # ISOLATED SUBNET
            iso_cidr = isolated_cidrs[i]
            iso_sub_name = namer.subnet("isolated", az, cidr=iso_cidr)
            iso_subnet = factory.create(
                "aws:ec2:Subnet",
                iso_sub_name,
                vpc_id=vpc_id,
                cidr_block=iso_cidr,
                availability_zone=az,
                map_public_ip_on_launch=False,
                tags={
                    "Name": iso_sub_name,
                    "Project": project_name,
                    "Environment": "prod",
                    "Tier": "isolated",
                    "AZ": az
                }
            )
            self.subnets[f"isolated-{idx}"] = iso_subnet
        
        # 7. NAT Gateway + EIP (after subnets are created)
        if enable_nat_gateway:
            for i in range(3):
                if i == 0 or nat_gateway_count == 3:
                    az = az_list[i]
                    idx = i + 1
                    pub_subnet = self.subnets[f"public-{idx}"]
                    
                    # Create EIP for NAT
                    nat_eip_name = namer.eip(az)
                    nat_eip = factory.create(
                        "aws:ec2:Eip",
                        nat_eip_name,
                        domain="vpc",
                        tags={
                            "Name": nat_eip_name,
                            "Project": project_name,
                            "Environment": "prod",
                            "AZ": az
                        }
                    )
                    
                    # Create NAT Gateway
                    nat_gw_name = namer.nat_gateway(az)
                    nat_gw = factory.create(
                        "aws:ec2:NatGateway",
                        nat_gw_name,
                        subnet_id=pub_subnet.id,
                        allocation_id=nat_eip.id,
                        tags={
                            "Name": nat_gw_name,
                            "Project": project_name,
                            "Environment": "prod",
                            "AZ": az
                        }
                    )
                    self.nat_gateways.append(nat_gw)
        
        # 8. Routes
        # Route to IGW for public route table
        factory.create(
            "aws:ec2:Route",
            namer.route("0.0.0.0/0", "igw"),
            route_table_id=public_rt_id,
            destination_cidr_block="0.0.0.0/0",
            gateway_id=igw_id
        )
        
        # Routes to NAT for private route tables (if enabled)
        if enable_nat_gateway:
            for i in range(3):
                idx = i + 1
                priv_rt = private_rts[i]
                # Use current AZ NAT if available, else fallback to first NAT
                target_nat = self.nat_gateways[i] if len(self.nat_gateways) > i else self.nat_gateways[0]
                factory.create(
                    "aws:ec2:Route",
                    namer.route("0.0.0.0/0", f"nat-{idx}"),
                    route_table_id=priv_rt.id,
                    destination_cidr_block="0.0.0.0/0",
                    nat_gateway_id=target_nat.id
                )
        
        # 9. Route Table Associations
        for i in range(3):
            idx = i + 1
            pub_subnet = self.subnets[f"public-{idx}"]
            priv_subnet = self.subnets[f"private-{idx}"]
            priv_rt = private_rts[i]
            
            # Associate public subnet with public route table
            factory.create(
                "aws:ec2:RouteTableAssociation",
                namer.route_table_association(f"public-{idx}", 1),
                subnet_id=pub_subnet.id,
                route_table_id=public_rt_id
            )
            
            # Associate private subnet with private route table
            factory.create(
                "aws:ec2:RouteTableAssociation",
                namer.route_table_association(f"private-{idx}", 1),
                subnet_id=priv_subnet.id,
                route_table_id=priv_rt.id
            )

        # 10. Interface VPC Endpoints (conditional, after subnets)
        if self.cfg.get('enable_ssm_endpoints', True):
            for svc in ['ssm', 'ssmmessages', 'ec2messages']:
                svc_name = namer.vpc_endpoint(svc, "interface")
                self.vpc_endpoints[svc] = factory.create(
                    "aws:ec2:VpcEndpoint",
                    svc_name,
                    vpc_id=vpc_id,
                    service_name=f"com.amazonaws.{region}.{svc}",
                    vpc_endpoint_type="Interface",
                    subnet_ids=private_subnet_ids,
                    security_group_ids=[self.security_groups['access'].id],
                    private_dns_enabled=True,
                    tags={
                        "Name": svc_name,
                        "Project": project_name,
                        "Environment": "prod"
                    }
                )

        # 11. RDS VPC Endpoint (conditional)
        if self.cfg.get('enable_rds_endpoint', False):
            rds_svc_name = namer.vpc_endpoint("rds", "interface")
            self.vpc_endpoints['rds'] = factory.create(
                "aws:ec2:VpcEndpoint",
                rds_svc_name,
                vpc_id=vpc_id,
                service_name=f"com.amazonaws.{region}.rds",
                vpc_endpoint_type="Interface",
                subnet_ids=private_subnet_ids,
                security_group_ids=[self.security_groups['access'].id],
                private_dns_enabled=True,
                tags={
                    "Name": rds_svc_name,
                    "Project": project_name,
                    "Environment": "prod"
                }
            )

        # 8. Flow Logs to S3 (Production-grade with lifecycle)
        if self.cfg.get('enable_flow_logs', True):
            flow_name = namer.flow_logs("vpc", "all")
            # Reuse existing bucket name on upgrade, generate deterministic name on first deploy
            existing_bucket = self.cfg.get('flow_logs_bucket_name', '') or self.cfg.get('flow_logs_bucket', '')
            if existing_bucket:
                bucket_name = existing_bucket
            else:
                import hashlib
                suffix = hashlib.sha256(project_name.encode()).hexdigest()[:6]
                bucket_name = f"{namer.s3_bucket('flowlogs')}-{suffix}"[:63]

            self._flow_logs_bucket_name = bucket_name

            # Create S3 Bucket for Flow Logs
            flow_logs_bucket = factory.create(
                "aws:s3:Bucket",
                bucket_name,
                bucket=bucket_name,
                force_destroy=True,
                tags={
                    "Name": bucket_name,
                    "Project": project_name,
                    "Environment": "prod",
                    "Purpose": "VPC Flow Logs"
                }
            )
            
            # Bucket Lifecycle Configuration for auto-deletion
            retention_days = self.cfg.get('flow_log_retention', 30)
            factory.create(
                "aws:s3:BucketLifecycleConfigurationV2",
                f"{bucket_name}-lifecycle",
                bucket=flow_logs_bucket.id,
                rules=[
                    {
                        "id": f"limit-lifespan-of-objects-{retention_days}-days",
                        "status": "Enabled",
                        "filter": {},
                        "expiration": {
                            "days": retention_days,
                            "expired_object_delete_marker": True
                        }
                    }
                ]
            )
            
            # Create Flow Logs pointing to S3
            self.flow_logs = factory.create(
                "aws:ec2:FlowLog",
                flow_name,
                vpc_id=vpc_id,
                traffic_type="ALL",
                log_destination_type="s3",
                log_destination=flow_logs_bucket.arn,
                max_aggregation_interval=600,
                destination_options={
                    "file_format": "plain-text",
                    "hive_compatible_partitions": False,
                    "per_hour_partition": False
                },
                tags={
                    "Name": flow_name,
                    "Project": project_name,
                    "Environment": "prod"
                }
            )

        # Exports
        pulumi.export("vpc_id", vpc_id)
        pulumi.export("vpc_name", vpc_resource_name)
        pulumi.export("vpc_cidr", cidr_block)
        if hasattr(self, '_flow_logs_bucket_name'):
            pulumi.export("flow_logs_bucket", self._flow_logs_bucket_name)
        pulumi.export("public_subnet_ids", [self.subnets[f"public-{i}"].id for i in range(1, 4)])
        pulumi.export("private_subnet_ids", [self.subnets[f"private-{i}"].id for i in range(1, 4)])
        pulumi.export("isolated_subnet_ids", [self.subnets[f"isolated-{i}"].id for i in range(1, 4)])
        pulumi.export("web_security_group_id", self.security_groups['web'].id)
        pulumi.export("app_security_group_id", self.security_groups['app'].id)
        pulumi.export("db_security_group_id", self.security_groups['db'].id)
        pulumi.export("access_security_group_id", self.security_groups['access'].id)
        
        return self.get_outputs()
    
    def get_outputs(self) -> Dict[str, Any]:
        """Return template outputs - Flattened for Pattern B compatibility"""
        outputs = {
            "vpc_id": self.vpc.id if self.vpc else None,
            "vpc_cidr": self.vpc.cidr_block if self.vpc else None,
            "public_subnet_ids": [self.subnets[f"public-{i}"].id for i in range(1, 4) if f"public-{i}" in self.subnets],
            "private_subnet_ids": [self.subnets[f"private-{i}"].id for i in range(1, 4) if f"private-{i}" in self.subnets],
            "isolated_subnet_ids": [self.subnets[f"isolated-{i}"].id for i in range(1, 4) if f"isolated-{i}" in self.subnets],
            
            # Map isolated to db_subnet_ids for RDS template
            "db_subnet_ids": [self.subnets[f"isolated-{i}"].id for i in range(1, 4) if f"isolated-{i}" in self.subnets],
        }
        
        # Flatten Security Groups
        if self.security_groups:
            outputs["web_security_group_id"] = self.security_groups.get('web').id if 'web' in self.security_groups else None
            outputs["app_security_group_id"] = self.security_groups.get('app').id if 'app' in self.security_groups else None
            outputs["db_security_group_id"] = self.security_groups.get('db').id if 'db' in self.security_groups else None
            outputs["access_security_group_id"] = self.security_groups.get('access').id if 'access' in self.security_groups else None
            
            # Keep nested for legacy reasons
            outputs["security_groups"] = {
                name: sg.id for name, sg in self.security_groups.items()
            }
            
        return outputs
    
    @classmethod
    def get_metadata(cls) -> Dict[str, Any]:
        """Get template metadata (SOURCE OF TRUTH for extractor - Pattern B)"""
        return {
            "name": "aws-vpc-prod",
            "title": "3-Tier Enterprise Network",
            "description": "Enterprise-grade networking foundation for production workloads. 3-AZ deployment with public/private/isolated subnets, 3 NAT Gateways for HA, S3-based flow logs with lifecycle policies, Network ACLs, and SSM endpoints.",
            "category": "networking",
            "version": "1.3.0",
            "author": "InnovativeApps",
            "cloud": "aws",
            "environment": "prod",
            "base_cost": "$110/month",
            "features": [
                "3-AZ Multi-AZ architecture for maximum uptime",
                "3-Tier Subnet design: Public (DMZ), Private (App), Isolated (DB)",
                "Redundant NAT Gateways (one per AZ) to eliminate single points of failure",
                "Network ACLs for defense-in-depth subnet-level security (enabled by default)",
                "S3-based VPC Flow Logs with 30-day lifecycle retention (enabled by default)",
                "SSM VPC Endpoints for secure Systems Manager access (enabled by default, +$42/mo)",
                "Private S3 and DynamoDB access via Gateway Endpoints (free)",
                "Zero-trust security pattern with strict security group templates",
                "Optional: RDS VPC Endpoint for database API calls (+$42/mo)"
            ],
            "tags": ["vpc", "networking", "production", "ha", "enterprise", "multi-az"],
            "deployment_time": "10-15 minutes",
            "complexity": "advanced",
            "use_cases": [
                "Production-grade High Availability Workloads",
                "Mission-Critical Applications",
                "Strict Network Isolation (3-tier)",
                "Redundant Outbound Connectivity",
                "Compliance-ready Observability",
                "Enterprise Web Applications"
            ],
            "pillars": [
                {
                    "title": "Operational Excellence",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Infrastructure as code deployment with comprehensive monitoring, automated configuration, and enterprise-grade operational visibility",
                    "practices": [
                        "Infrastructure as Code with Pulumi for repeatable deployments",
                        "CloudWatch-based VPC Flow Logs for operational visibility",
                        "Configurable resource naming conventions for easy identification",
                        "VPC endpoints for centralized service access",
                        "Automated subnet and routing table configuration across 3 AZs",
                        "SSM endpoints for secure instance management"
                    ]
                },
                {
                    "title": "Security",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Defense-in-depth with network segmentation, least-privilege access, and comprehensive audit logging",
                    "practices": [
                        "Multi-tier security groups (web, app, database, access)",
                        "Private subnets for application and database tiers",
                        "VPC Flow Logs to CloudWatch for security monitoring and compliance",
                        "Isolated tier for maximum security database workloads",
                        "Network ACLs for additional subnet-level protection",
                        "VPC endpoints to reduce internet exposure",
                        "SSM endpoints for secure instance access without bastion hosts"
                    ]
                },
                {
                    "title": "Reliability",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Multi-AZ architecture with redundant NAT infrastructure and fault-tolerant design for production workloads",
                    "practices": [
                        "3 Availability Zones for maximum fault tolerance",
                        "Redundant internet connectivity via Internet Gateway",
                        "3 NAT Gateways (one per AZ) for outbound HA",
                        "Isolated tier for critical database workloads",
                        "Multiple subnets per tier across availability zones",
                        "Automatic failover for NAT routing"
                    ]
                },
                {
                    "title": "Performance Efficiency",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Optimizes network performance with proper subnet design, multi-AZ distribution, and VPC endpoint acceleration",
                    "practices": [
                        "Dedicated subnets per tier for traffic isolation",
                        "3 NAT Gateways for distributed high-bandwidth outbound connectivity",
                        "VPC endpoints for direct AWS service access",
                        "Gateway endpoints for S3 and DynamoDB to reduce latency",
                        "Interface endpoints for SSM to minimize internet routing",
                        "Configurable CIDR ranges to avoid IP exhaustion"
                    ]
                },
                {
                    "title": "Cost Optimization",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Production-grade infrastructure with optimized resource sizing and configurable NAT deployment options",
                    "practices": [
                        "Gateway VPC endpoints (S3, DynamoDB) are free",
                        "CloudWatch logs with configurable retention to manage costs",
                        "Optional single NAT Gateway mode for cost reduction (1 vs 3)",
                        "Right-sized subnets to minimize IP address waste",
                        "Configurable interface endpoints to balance cost vs security"
                    ]
                },
                {
                    "title": "Sustainability",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Balances high availability with efficient resource utilization through smart deployment patterns",
                    "practices": [
                        "Gateway VPC endpoints eliminate data transfer infrastructure",
                        "Right-sized network resources to avoid over-provisioning",
                        "Regional AWS services reduce data travel distances",
                        "Configurable NAT count for workload-appropriate redundancy"
                    ]
                }
            ]
        }
    
    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        """Get configuration schema (SOURCE OF TRUTH for extractor - STANDARD FORMAT)"""
        return {
            "type": "object",
            "properties": {
                "cidr_block": {
                    "type": "string",
                    "default": "random",
                    "title": "VPC CIDR Block",
                    "description": "IPv4 CIDR block for the VPC (use 'random' for auto-generated)",
                    "order": 10,
                    "group": "Network Configuration"
                },
                "enable_dns_support": {
                    "type": "boolean",
                    "default": True,
                    "title": "Enable DNS Support",
                    "description": "Enable DNS resolution in the VPC",
                    "order": 11,
                    "group": "Network Configuration"
                },
                "enable_dns_hostnames": {
                    "type": "boolean",
                    "default": True,
                    "title": "Enable DNS Hostnames",
                    "description": "Enable DNS hostnames for instances",
                    "order": 12,
                    "group": "Network Configuration"
                },
                "az_1": {
                    "type": "string",
                    "default": "",
                    "title": "Availability Zone 1",
                    "description": "First availability zone (auto-selected if empty)",
                    "order": 20,
                    "group": "Availability Zones"
                },
                "az_2": {
                    "type": "string",
                    "default": "",
                    "title": "Availability Zone 2",
                    "description": "Second availability zone (auto-selected if empty)",
                    "order": 21,
                    "group": "Availability Zones"
                },
                "az_3": {
                    "type": "string",
                    "default": "",
                    "title": "Availability Zone 3",
                    "description": "Third availability zone (auto-selected if empty)",
                    "order": 22,
                    "group": "Availability Zones"
                },
                "enable_nat_gateway": {
                    "type": "boolean",
                    "default": True,
                    "title": "Enable NAT Gateway",
                    "description": "Creates NAT Gateway(s) for private subnet internet access",
                    "order": 100,
                    "group": "High Availability & Cost",
                    "cost_impact": "+$96/month"
                },
                "nat_gateway_count": {
                    "type": "integer",
                    "default": 3,
                    "title": "NAT Gateway Count",
                    "description": "Number of NAT Gateways (1 or 3 for HA)",
                    "order": 101,
                    "group": "High Availability & Cost",
                    "cost_impact": "+$32-96/month"
                },
                "enable_flow_logs": {
                    "type": "boolean",
                    "default": True,
                    "title": "Enable VPC Flow Logs",
                    "description": "Capture network traffic logs to S3 for security monitoring",
                    "order": 110,
                    "group": "High Availability & Cost",
                    "cost_impact": "+$3/month"
                },
                "flow_log_retention": {
                    "type": "integer",
                    "default": 30,
                    "title": "Flow Logs Retention (days)",
                    "description": "How long to retain flow logs in S3 before auto-deletion",
                    "order": 111,
                    "group": "High Availability & Cost"
                },
                "enable_nacls": {
                    "type": "boolean",
                    "default": True,
                    "title": "Enable Network ACLs",
                    "description": "Create Network ACLs for subnet-level security",
                    "order": 120,
                    "group": "Security Settings",
                    "cost_impact": "$0/month"
                },

                "enable_rds_endpoint": {
                    "type": "boolean",
                    "default": False,
                    "title": "Enable RDS VPC Endpoint",
                    "description": "Interface endpoint for RDS API calls",
                    "order": 132,
                    "group": "VPC Endpoints",
                    "cost_impact": "+$42/month"
                },
                "enable_ssm_endpoints": {
                    "type": "boolean",
                    "default": True,
                    "title": "Enable SSM VPC Endpoints",
                    "description": "Private endpoints for AWS Systems Manager",
                    "order": 133,
                    "group": "VPC Endpoints",
                    "cost_impact": "+$126/month"
                },
                "ssh_access_ip": {
                    "type": "string",
                    "default": "",
                    "title": "SSH Access IP (Optional)",
                    "description": "Your IP for SSH/RDP access (e.g., 1.2.3.4/32)",
                    "order": 140,
                    "group": "Security Settings"
                }
            },
            "required": ["project_name", "region"]
        }
