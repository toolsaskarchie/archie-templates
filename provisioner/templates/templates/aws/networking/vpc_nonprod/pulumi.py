"""
VPC Simple Non-Prod Template - Single AZ Cost-Optimized

Ultra cost-optimized networking foundation for non-production environments.
Single AZ deployment to minimize costs while maintaining functionality.

Base cost ($20/mo):
- 1 AZ deployment
- 1 NAT Gateway
- Public, private, and optional isolated subnets
- Free VPC endpoints (S3, DynamoDB)
- S3-based Flow Logs (cheaper than CloudWatch)
- Security Groups for web/app/db tiers

Optional features:
- Isolated tier for databases (+$0/mo)
- RDS VPC endpoint (+$14/mo)
- SSM VPC endpoints (+$42/mo)
- VPC Flow Logs (+$1/mo)
"""

from typing import Any, Dict, List, Optional
from pathlib import Path
import json
import pulumi
import pulumi_aws as aws

# Import Archie utils
from provisioner.utils.aws import ResourceNamer
from provisioner.utils.aws.cidr_utils import generate_random_vpc_cidr, calculate_subnet_cidrs
from provisioner.utils.aws.tags import get_standard_tags
from provisioner.templates.base import template_registry, InfrastructureTemplate
from provisioner.templates.template_config import TemplateConfig
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory


@template_registry("aws-vpc-nonprod")
class VPCSimpleNonprodTemplate(InfrastructureTemplate):
    """
    VPC Simple Non-Prod Template - Single AZ Cost-Optimized
    
    Ultra cost-optimized VPC for non-production environments.
    All resources created via factory pattern - no atomics, no ui-manifest.
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
        """Initialize VPC Simple Nonprod template"""
        raw_config = config or aws or kwargs or {}
        
        if name is None:
            name = (
                raw_config.get('project_name') or 
                raw_config.get('projectName') or
                raw_config.get('parameters', {}).get('aws', {}).get('project_name') or
                'vpc-nonprod'
            )
        
        super().__init__(name, raw_config)
        
        # Load template configuration
        template_dir = Path(__file__).parent
        self.cfg = TemplateConfig(template_dir, raw_config)
        self.config = raw_config
        
        # Resource references
        self.vpc: Optional[aws.ec2.Vpc] = None
        self.igw: Optional[aws.ec2.InternetGateway] = None
        self.nat_gateway: Optional[aws.ec2.NatGateway] = None
        self.subnets = {}
        self.route_tables = {}
        self.security_groups = {}
        self.vpc_endpoints = {}
        self.flow_logs_bucket: Optional[aws.s3.Bucket] = None
        self.flow_log: Optional[aws.ec2.FlowLog] = None
    
    def create_infrastructure(self) -> Dict[str, Any]:
        """Deploy VPC infrastructure (implements abstract method)"""
        return self.create()
    
    def create(self) -> Dict[str, Any]:
        """Deploy complete VPC infrastructure using factory pattern"""
        
        # Initialize namer with all required parameters
        environment = self.cfg.get('environment', 'nonprod')
        namer = ResourceNamer(
            project=self.cfg.project_name,
            environment=environment,
            region=self.cfg.region,
            template="aws-vpc-nonprod"
        )
        
        project_name = self.cfg.project_name
        region_short = self.cfg.region.replace('-', '')
        
        # DEBUG: what does the template actually see?
        print(f"[VPC-DEBUG] raw config keys: {list(self.config.keys()) if isinstance(self.config, dict) else 'NOT DICT'}")
        print(f"[VPC-DEBUG] cfg.parameters: {self.cfg.parameters}")
        print(f"[VPC-DEBUG] use_custom_cidr={self.cfg.get('use_custom_cidr')}, custom_cidr_block={self.cfg.get('custom_cidr_block')}, vpc_cidr={self.cfg.get('vpc_cidr')}, vpc_name={self.cfg.get('vpc_name')}")

        # Generate random CIDR or use custom CIDR based on configuration
        use_custom = self.cfg.get('use_custom_cidr', False)
        if use_custom and self.cfg.get('custom_cidr_block'):
            vpc_cidr = self.cfg.custom_cidr_block
            print(f"[VPC TEMPLATE] Using custom VPC CIDR: {vpc_cidr}")
        else:
            vpc_cidr = generate_random_vpc_cidr(prefix_length=16)
            print(f"[VPC TEMPLATE] Generated random VPC CIDR: {vpc_cidr}")
        
        # Calculate subnet CIDRs from VPC CIDR (3 /20 subnets for public, private, isolated)
        subnet_cidrs = calculate_subnet_cidrs(vpc_cidr, count=3, subnet_prefix=20)
        public_cidr = subnet_cidrs[0]
        private_cidr = subnet_cidrs[1]
        isolated_cidr = subnet_cidrs[2]
        
        # Standard Archie tags using utility function
        tags = get_standard_tags(
            project=self.cfg.project_name,
            environment=environment,
            template="aws-vpc-nonprod"
        )
        tags.update(self.cfg.get('tags', {}))
        
        # =================================================================
        # LAYER 1: VPC Core
        # =================================================================
        
        vpc_name = self.cfg.get('vpc_name') or namer.vpc(cidr=vpc_cidr)
        self.vpc = factory.create(
            "aws:ec2:Vpc",
            vpc_name,
            cidr_block=vpc_cidr,
            enable_dns_support=self._to_bool(self.config.get('enable_dns_support', self.config.get('parameters', {}).get('enable_dns_support', True))),
            enable_dns_hostnames=self._to_bool(self.config.get('enable_dns_hostnames', self.config.get('parameters', {}).get('enable_dns_hostnames', True))),
            instance_tenancy=self.cfg.instance_tenancy,
            tags={**tags, "Name": vpc_name}
        )
        
        vpc_id = self.vpc.id
        
        # =================================================================
        # LAYER 2: Internet Gateway
        # =================================================================
        
        igw_name = namer.internet_gateway()
        self.igw = factory.create(
            "aws:ec2:InternetGateway",
            igw_name,
            vpc_id=vpc_id,
            tags={**tags, "Name": igw_name}
        )
        
        igw_id = self.igw.id
        
        # =================================================================
        # LAYER 3: Route Tables (Created early to match prod order)
        # =================================================================
        
        # =================================================================
        # LAYER 3: Route Tables (Created early to match prod order)
        # =================================================================
        
        # Public Route Table
        public_rt_name = namer.route_table("public")
        self.route_tables['public'] = factory.create(
            "aws:ec2:RouteTable",
            public_rt_name,
            vpc_id=vpc_id,
            tags={**tags, "Name": public_rt_name, "Tier": "public"}
        )
        
        # Private Route Table
        private_rt_name = namer.route_table("private")
        self.route_tables['private'] = factory.create(
            "aws:ec2:RouteTable",
            private_rt_name,
            vpc_id=vpc_id,
            tags={**tags, "Name": private_rt_name, "Tier": "private"}
        )
        
        # Isolated Route Table (conditional)
        if self.cfg.enable_isolated_tier:
            isolated_rt_name = namer.route_table("isolated")
            self.route_tables['isolated'] = factory.create(
                "aws:ec2:RouteTable",
                isolated_rt_name,
                vpc_id=vpc_id,
                tags={**tags, "Name": isolated_rt_name, "Tier": "isolated"}
            )
        
        # =================================================================
        # LAYER 4: VPC Endpoints (Gateway - free, always created)
        # =================================================================
        
        # S3 Gateway Endpoint (free)
        s3_endpoint_name = namer.vpc_endpoint("s3", "gateway")
        self.vpc_endpoints['s3'] = factory.create(
            "aws:ec2:VpcEndpoint",
            s3_endpoint_name,
            vpc_id=vpc_id,
            service_name=f"com.amazonaws.{self.cfg.region}.s3",
            vpc_endpoint_type="Gateway",
            route_table_ids=[
                self.route_tables['public'].id,
                self.route_tables['private'].id,
            ] + ([self.route_tables['isolated'].id] if self.cfg.enable_isolated_tier else []),
            tags={**tags, "Name": s3_endpoint_name}
        )
        
        # DynamoDB Gateway Endpoint (free)
        dynamodb_endpoint_name = namer.vpc_endpoint("dynamodb", "gateway")
        self.vpc_endpoints['dynamodb'] = factory.create(
            "aws:ec2:VpcEndpoint",
            dynamodb_endpoint_name,
            vpc_id=vpc_id,
            service_name=f"com.amazonaws.{self.cfg.region}.dynamodb",
            vpc_endpoint_type="Gateway",
            route_table_ids=[
                self.route_tables['public'].id,
                self.route_tables['private'].id,
            ] + ([self.route_tables['isolated'].id] if self.cfg.enable_isolated_tier else []),
            tags={**tags, "Name": dynamodb_endpoint_name}
        )
        
        # =================================================================
        # LAYER 5: Security Groups (3-tier architecture)
        # =================================================================
        
        # =================================================================
        # LAYER 5: Security Groups (3-tier architecture)
        # =================================================================
        
        # Web Tier Security Group
        web_sg_name = namer.security_group("web", ports=[80, 443])
        self.security_groups['web'] = factory.create(
            "aws:ec2:SecurityGroup",
            web_sg_name,
            vpc_id=vpc_id,
            description="Security group for web tier (HTTP/HTTPS)",
            ingress=[
                {
                    "protocol": "tcp",
                    "from_port": 80,
                    "to_port": 80,
                    "cidr_blocks": ["0.0.0.0/0"],
                    "description": "HTTP from internet"
                },
                {
                    "protocol": "tcp",
                    "from_port": 443,
                    "to_port": 443,
                    "cidr_blocks": ["0.0.0.0/0"],
                    "description": "HTTPS from internet"
                }
            ],
            egress=[
                {
                    "protocol": "-1",
                    "from_port": 0,
                    "to_port": 0,
                    "cidr_blocks": ["0.0.0.0/0"],
                    "description": "Allow all outbound"
                }
            ],
            tags={**tags, "Name": web_sg_name, "Tier": "web"}
        )
        
        # App Tier Security Group
        app_sg_name = namer.security_group("app", ports=[3000, 8080])
        self.security_groups['app'] = factory.create(
            "aws:ec2:SecurityGroup",
            app_sg_name,
            vpc_id=vpc_id,
            description="Security group for application tier",
            ingress=[
                {
                    "protocol": "tcp",
                    "from_port": 3000,
                    "to_port": 3000,
                    "security_groups": [self.security_groups['web'].id],
                    "description": "App traffic from web tier"
                },
                {
                    "protocol": "tcp",
                    "from_port": 8080,
                    "to_port": 8080,
                    "security_groups": [self.security_groups['web'].id],
                    "description": "Alt app port from web tier"
                }
            ],
            egress=[
                {
                    "protocol": "-1",
                    "from_port": 0,
                    "to_port": 0,
                    "cidr_blocks": ["0.0.0.0/0"],
                    "description": "Allow all outbound"
                }
            ],
            tags={**tags, "Name": app_sg_name, "Tier": "app"}
        )
        
        # Database Tier Security Group
        db_sg_name = namer.security_group("db", ports=[3306, 5432])
        self.security_groups['db'] = factory.create(
            "aws:ec2:SecurityGroup",
            db_sg_name,
            vpc_id=vpc_id,
            description="Security group for database tier",
            ingress=[
                {
                    "protocol": "tcp",
                    "from_port": 3306,
                    "to_port": 3306,
                    "security_groups": [self.security_groups['app'].id],
                    "description": "MySQL from app tier"
                },
                {
                    "protocol": "tcp",
                    "from_port": 5432,
                    "to_port": 5432,
                    "security_groups": [self.security_groups['app'].id],
                    "description": "PostgreSQL from app tier"
                },
                {
                    "protocol": "tcp",
                    "from_port": 1433,
                    "to_port": 1433,
                    "security_groups": [self.security_groups['app'].id],
                    "description": "SQL Server from app tier"
                }
            ],
            egress=[
                {
                    "protocol": "-1",
                    "from_port": 0,
                    "to_port": 0,
                    "cidr_blocks": ["0.0.0.0/0"],
                    "description": "Allow all outbound"
                }
            ],
        )
        
        # Access Security Group (Management/SSH)
        # Only created when enable_ssh_access is enabled
        enable_ssh = self.cfg.get('enable_ssh_access', False)
        if enable_ssh:
            ssh_access_ip = self.cfg.get('ssh_access_ip', '1.2.3.4/32')
            access_sg_ingress = []
            
            if ssh_access_ip:
                # Handle single IP (string) or list for backward compatibility
                allowed_ips = [ssh_access_ip] if isinstance(ssh_access_ip, str) else ssh_access_ip
                
                for ip in allowed_ips:
                    if not ip: continue
                    cidr_ip = ip if '/' in ip else f"{ip}/32"
                    access_sg_ingress.append({
                        "protocol": "tcp",
                        "from_port": 22,
                        "to_port": 22,
                        "cidr_blocks": [cidr_ip],
                        "description": f"SSH from {cidr_ip}"
                    })
                    access_sg_ingress.append({
                        "protocol": "tcp",
                        "from_port": 3389,
                        "to_port": 3389,
                        "cidr_blocks": [cidr_ip],
                        "description": f"RDP from {cidr_ip}"
                    })

            access_sg_name = namer.security_group(purpose="access")
            self.security_groups['access'] = factory.create(
                "aws:ec2:SecurityGroup",
                access_sg_name,
                vpc_id=vpc_id,
                description="Management access security group (SSH/RDP)",
                ingress=access_sg_ingress,
                egress=[
                    {
                        "protocol": "-1",
                        "from_port": 0,
                        "to_port": 0,
                        "cidr_blocks": ["0.0.0.0/0"],
                        "description": "Allow all outbound"
                    }
                ],
                tags={**tags, "Name": access_sg_name, "Tier": "management"}
            )
        
        # =================================================================
        # LAYER 6: Subnets (Single AZ)
        # =================================================================
        
        az = self.cfg.az_1 or f"{self.cfg.region}a"
        
        # Public Subnet
        public_subnet_name = namer.subnet("public", az, cidr=public_cidr)
        self.subnets['public'] = factory.create(
            "aws:ec2:Subnet",
            public_subnet_name,
            vpc_id=vpc_id,
            cidr_block=public_cidr,
            availability_zone=az,
            map_public_ip_on_launch=True,
            tags={**tags, "Name": public_subnet_name, "Tier": "public"}
        )

        # Private Subnet
        private_subnet_name = namer.subnet("private", az, cidr=private_cidr)
        self.subnets['private'] = factory.create(
            "aws:ec2:Subnet",
            private_subnet_name,
            vpc_id=vpc_id,
            cidr_block=private_cidr,
            availability_zone=az,
            map_public_ip_on_launch=False,
            tags={**tags, "Name": private_subnet_name, "Tier": "private"}
        )

        # Isolated Subnet (conditional)
        if self.cfg.enable_isolated_tier:
            isolated_subnet_name = namer.subnet("isolated", az, cidr=isolated_cidr)
            self.subnets['isolated'] = factory.create(
                "aws:ec2:Subnet",
                isolated_subnet_name,
                vpc_id=vpc_id,
                cidr_block=isolated_cidr,
                availability_zone=az,
                map_public_ip_on_launch=False,
                tags={**tags, "Name": isolated_subnet_name, "Tier": "isolated"}
            )
        
        # =================================================================
        # LAYER 7: NAT Gateway (Single for nonprod) - CONDITIONAL
        # =================================================================
        
        if self.cfg.get('enable_nat_gateway', True):
            eip_name = namer.eip(az)
            nat_eip = factory.create(
                "aws:ec2:Eip",
                eip_name,
                domain="vpc",
                tags={**tags, "Name": eip_name}
            )
            
            nat_name = namer.nat_gateway(az)
            self.nat_gateway = factory.create(
                "aws:ec2:NatGateway",
                nat_name,
                subnet_id=self.subnets['public'].id,
                allocation_id=nat_eip.id,
                tags={**tags, "Name": nat_name}
            )
        
        # =================================================================
        # LAYER 8: Routes
        # =================================================================
        
        # Public route to IGW
        public_route_name = namer.route("0.0.0.0/0", "igw")
        factory.create(
            "aws:ec2:Route",
            public_route_name,
            route_table_id=self.route_tables['public'].id,
            destination_cidr_block="0.0.0.0/0",
            gateway_id=igw_id
        )
        
        # Private route to NAT (only if NAT Gateway exists)
        if self.cfg.get('enable_nat_gateway', True) and self.nat_gateway:
            private_route_name = namer.route("0.0.0.0/0", "nat")
            factory.create(
                "aws:ec2:Route",
                private_route_name,
                route_table_id=self.route_tables['private'].id,
                destination_cidr_block="0.0.0.0/0",
                nat_gateway_id=self.nat_gateway.id
            )
        
        
        # No route for isolated tier - VPC-only traffic
        
        # =================================================================
        # LAYER 9: Route Table Associations
        # =================================================================
        
        # Public subnet association
        factory.create(
            "aws:ec2:RouteTableAssociation",
            namer.route_table_association("public", 1),
            subnet_id=self.subnets['public'].id,
            route_table_id=self.route_tables['public'].id
        )
        
        # Private subnet association
        factory.create(
            "aws:ec2:RouteTableAssociation",
            namer.route_table_association("private", 1),
            subnet_id=self.subnets['private'].id,
            route_table_id=self.route_tables['private'].id
        )
        
        # Isolated subnet association (conditional)
        if self.cfg.enable_isolated_tier:
            factory.create(
                "aws:ec2:RouteTableAssociation",
                namer.route_table_association("isolated", 1),
                subnet_id=self.subnets['isolated'].id,
                route_table_id=self.route_tables['isolated'].id
            )
        
        # =================================================================
        # LAYER 10: VPC Endpoints (Interface - conditional, paid)
        # =================================================================
        # =================================================================
        # LAYER 10: VPC Endpoints (Interface - conditional, paid)
        # =================================================================
        
        # RDS Interface Endpoint (optional, +$14/mo)
        if self.cfg.enable_rds_endpoint:
            rds_endpoint_name = namer.vpc_endpoint("rds", "interface")
            self.vpc_endpoints['rds'] = factory.create(
                "aws:ec2:VpcEndpoint",
                rds_endpoint_name,
                vpc_id=vpc_id,
                service_name=f"com.amazonaws.{self.cfg.region}.rds",
                vpc_endpoint_type="Interface",
                subnet_ids=[self.subnets['private'].id],
                security_group_ids=[self.security_groups['db'].id],
                private_dns_enabled=True,
                tags={**tags, "Name": rds_endpoint_name}
            )
        
        # SSM Interface Endpoints (optional, +$14/mo each)
        if self.cfg.enable_ssm_endpoints:
            # SSM endpoint
            ssm_endpoint_name = namer.vpc_endpoint("ssm", "interface")
            self.vpc_endpoints['ssm'] = factory.create(
                "aws:ec2:VpcEndpoint",
                ssm_endpoint_name,
                vpc_id=vpc_id,
                service_name=f"com.amazonaws.{self.cfg.region}.ssm",
                vpc_endpoint_type="Interface",
                subnet_ids=[self.subnets['private'].id],
                private_dns_enabled=True,
                tags={**tags, "Name": ssm_endpoint_name}
            )
            
            # SSM Messages endpoint
            ssm_messages_endpoint_name = namer.vpc_endpoint("ssmmessages", "interface")
            self.vpc_endpoints['ssmmessages'] = factory.create(
                "aws:ec2:VpcEndpoint",
                ssm_messages_endpoint_name,
                vpc_id=vpc_id,
                service_name=f"com.amazonaws.{self.cfg.region}.ssmmessages",
                vpc_endpoint_type="Interface",
                subnet_ids=[self.subnets['private'].id],
                private_dns_enabled=True,
                tags={**tags, "Name": ssm_messages_endpoint_name}
            )
            
            # EC2 Messages endpoint
            ec2_messages_endpoint_name = namer.vpc_endpoint("ec2messages", "interface")
            self.vpc_endpoints['ec2messages'] = factory.create(
                "aws:ec2:VpcEndpoint",
                ec2_messages_endpoint_name,
                vpc_id=vpc_id,
                service_name=f"com.amazonaws.{self.cfg.region}.ec2messages",
                vpc_endpoint_type="Interface",
                subnet_ids=[self.subnets['private'].id],
                private_dns_enabled=True,
                tags={**tags, "Name": ec2_messages_endpoint_name}
            )
        
        # =================================================================
        # LAYER 10: VPC Flow Logs (S3-based, cheaper than CloudWatch)
        # =================================================================
        
        if self.cfg.enable_flow_logs:
            # Reuse existing bucket name on upgrade, generate deterministic name on first deploy
            existing_bucket = self.cfg.get('flow_logs_bucket_name', '') or self.cfg.get('flow_logs_bucket', '')
            if existing_bucket:
                bucket_name = existing_bucket
            else:
                import hashlib
                suffix = hashlib.sha256(self.name.encode()).hexdigest()[:6]
                bucket_name = f"{namer.s3_bucket('flowlogs')}-{suffix}"[:63]
            self.flow_logs_bucket = factory.create(
                "aws:s3:Bucket",
                bucket_name,
                bucket=bucket_name,
                force_destroy=True,
                tags={**tags, "Name": bucket_name, "Purpose": "VPC Flow Logs"}
            )
            
            # Bucket lifecycle policy - delete after retention period
            factory.create(
                "aws:s3:BucketLifecycleConfigurationV2",
                f"{bucket_name}-lifecycle",
                bucket=self.flow_logs_bucket.id,
                rules=[{
                    "id": "delete-old-flow-logs",
                    "status": "Enabled",
                    "expiration": {
                        "days": self.cfg.flow_log_retention
                    }
                }]
            )
            
            # Create Flow Log
            flow_log_name = namer.flow_logs("vpc", "all")
            self.flow_log = factory.create(
                "aws:ec2:FlowLog",
                flow_log_name,
                vpc_id=vpc_id,
                traffic_type="ALL",
                log_destination_type="s3",
                log_destination=self.flow_logs_bucket.arn.apply(lambda arn: f"{arn}/"),
                max_aggregation_interval=600,  # 10 minutes
                tags={**tags, "Name": flow_log_name}
            )
        
        # =================================================================
        # Outputs
        # =================================================================
        
        pulumi.export("vpc_id", self.vpc.id)
        pulumi.export("vpc_name", vpc_name)
        pulumi.export("vpc_cidr", self.vpc.cidr_block)
        pulumi.export("vpc_arn", self.vpc.arn)
        
        pulumi.export("internet_gateway_id", self.igw.id)
        pulumi.export("nat_gateway_id", self.nat_gateway.id)
        
        pulumi.export("public_subnet_id", self.subnets['public'].id)
        pulumi.export("private_subnet_id", self.subnets['private'].id)
        if self.cfg.enable_isolated_tier:
            pulumi.export("isolated_subnet_id", self.subnets['isolated'].id)
        
        pulumi.export("public_route_table_id", self.route_tables['public'].id)
        pulumi.export("private_route_table_id", self.route_tables['private'].id)
        if self.cfg.enable_isolated_tier:
            pulumi.export("isolated_route_table_id", self.route_tables['isolated'].id)
        
        pulumi.export("security_group_web_id", self.security_groups['web'].id)
        pulumi.export("security_group_app_id", self.security_groups['app'].id)
        pulumi.export("security_group_db_id", self.security_groups['db'].id)
        
        pulumi.export("vpc_endpoint_s3_id", self.vpc_endpoints['s3'].id)
        pulumi.export("vpc_endpoint_dynamodb_id", self.vpc_endpoints['dynamodb'].id)
        
        if self.cfg.enable_flow_logs:
            pulumi.export("flow_logs_bucket", self.flow_logs_bucket.id)
            pulumi.export("flow_log_id", self.flow_log.id)
        
        return {
            "vpc_id": self.vpc.id,
            "vpc_cidr": self.vpc.cidr_block,
            "public_subnet_id": self.subnets['public'].id,
            "private_subnet_id": self.subnets['private'].id,
            "nat_gateway_id": self.nat_gateway.id,
            "security_groups": {
                "web": self.security_groups['web'].id,
                "app": self.security_groups['app'].id,
                "db": self.security_groups['db'].id
            }
        }    
    def get_outputs(self) -> Dict[str, Any]:
        """Get outputs for this template (implements abstract method) - Flattened for Pattern B"""
        outputs = {
            "vpc_id": self.vpc.id if self.vpc else None,
            "vpc_cidr": self.vpc.cidr_block if self.vpc else None,
            
            # Singular IDs (Backward compatibility)
            "public_subnet_id": self.subnets.get('public').id if 'public' in self.subnets else None,
            "private_subnet_id": self.subnets.get('private').id if 'private' in self.subnets else None,
            
            # Plural IDs (Standard for cross-template composition)
            "public_subnet_ids": [self.subnets.get('public').id] if 'public' in self.subnets else [],
            "private_subnet_ids": [self.subnets.get('private').id] if 'private' in self.subnets else [],
            
            "nat_gateway_id": self.nat_gateway.id if self.nat_gateway else None,
        }
        
        # Add isolated/db subnet info
        if 'isolated' in self.subnets:
            outputs["isolated_subnet_id"] = self.subnets['isolated'].id
            outputs["isolated_subnet_ids"] = [self.subnets['isolated'].id]
            # Map isolated to db_subnet_ids for RDS template
            outputs["db_subnet_ids"] = [self.subnets['isolated'].id]
        elif 'private' in self.subnets:
            # Fallback for RDS
            outputs["db_subnet_ids"] = [self.subnets['private'].id]
        
        # Flatten Security Groups for easy access in Layer 4 templates
        if self.security_groups:
            outputs["web_security_group_id"] = self.security_groups.get('web').id if 'web' in self.security_groups else None
            outputs["app_security_group_id"] = self.security_groups.get('app').id if 'app' in self.security_groups else None
            outputs["db_security_group_id"] = self.security_groups.get('db').id if 'db' in self.security_groups else None
            outputs["access_security_group_id"] = self.security_groups.get('access').id if 'access' in self.security_groups else None
            
            # Keep nested for legacy reasons if needed, but flat is preferred
            outputs["security_groups"] = {
                "web": outputs["web_security_group_id"],
                "app": outputs["app_security_group_id"],
                "db": outputs["db_security_group_id"],
                "access": outputs["access_security_group_id"]
            }
        
        return outputs
    
    @classmethod
    def get_metadata(cls) -> Dict[str, Any]:
        """
        Get template metadata (SOURCE OF TRUTH for extractor).
        This metadata will be extracted by pulumi-extractor.py to generate template.yaml
        """
        return {
            "name": "aws-vpc-nonprod",
            "title": "Single-AZ VPC Foundation",
            "description": "Ultra cost-optimized networking foundation for development environments. Single AZ with public/private subnets, 1 NAT Gateway, S3-based flow logs.",
            "category": "networking",
            "version": "3.0.0",
            "author": "InnovativeApps",
            "cloud": "aws",
            "environment": "nonprod",
            "base_cost": "$20/month",
            "features": [
                "Single-AZ deployment for cost optimization",
                "1 NAT Gateway (saves $32/mo vs multi-AZ)",
                "Public and private subnets",
                "Security Groups for web/app/db tiers",
                "S3-based VPC Flow Logs (enabled by default, 7-day retention)",
                "Optional: Isolated tier for databases",
                "Optional: RDS VPC Endpoint (+$14/mo)",
                "Optional: SSM VPC Endpoints for Session Manager (+$42/mo)"
            ],
            "tags": ["vpc", "networking", "nonprod", "single-az", "cost-optimized"],
            "deployment_time": "4-6 minutes",
            "complexity": "beginner",
            "use_cases": [
                "Development and Testing Environments",
                "Multi-tier Web Applications",
                "Microservices Architecture",
                "Secure Private Databases",
                "Cost-Optimized Staging Environments"
            ],
            "pillars": [
                {
                    "title": "Operational Excellence",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Enables infrastructure as code deployment with automated configuration and monitoring capabilities",
                    "practices": [
                        "Infrastructure as Code with Pulumi for repeatable deployments",
                        "VPC Flow Logs for operational visibility and troubleshooting",
                        "Configurable resource naming conventions for easy identification",
                        "Optional VPC endpoints for centralized service access",
                        "Automated subnet and routing table configuration"
                    ]
                },
                {
                    "title": "Security",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Defense-in-depth with network segmentation and least-privilege access",
                    "practices": [
                        "Multi-tier security groups (web, app, database)",
                        "Private subnets for application and database tiers",
                        "VPC Flow Logs for network monitoring and compliance",
                        "Optional isolated tier for maximum security workloads",
                        "Network ACLs for additional subnet-level protection"
                    ]
                },
                {
                    "title": "Reliability",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Simplified architecture for dev/test environments with core networking components",
                    "practices": [
                        "Redundant internet connectivity via Internet Gateway",
                        "NAT Gateway for reliable outbound internet access",
                        "Optional isolated tier for database workloads",
                        "Multiple subnets across availability zones"
                    ]
                },
                {
                    "title": "Performance Efficiency",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Optimizes network performance with proper subnet design and routing configurations",
                    "practices": [
                        "Dedicated subnets per tier for traffic isolation",
                        "NAT Gateway for high-bandwidth outbound connectivity",
                        "Optional VPC endpoints for direct AWS service access",
                        "Configurable CIDR ranges to avoid IP exhaustion"
                    ]
                },
                {
                    "title": "Cost Optimization",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Single-AZ deployment with optimized resource sizing for non-production workloads",
                    "practices": [
                        "1 NAT Gateway instead of multi-AZ (saves $32/mo)",
                        "S3-based flow logs instead of CloudWatch (saves ~$10/mo)",
                        "Optional VPC endpoints to reduce data transfer costs",
                        "Right-sized subnets to minimize IP address waste"
                    ]
                },
                {
                    "title": "Sustainability",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Minimizes environmental impact through efficient resource utilization and regional service usage",
                    "practices": [
                        "Single-AZ design reduces redundant resource consumption",
                        "Gateway VPC endpoints eliminate data transfer infrastructure",
                        "Right-sized network resources to avoid over-provisioning",
                        "Regional AWS services reduce data travel distances"
                    ]
                }
            ]
        }
    
    @classmethod  
    def get_config_schema(cls) -> Dict[str, Any]:
        """
        Get configuration schema (SOURCE OF TRUTH for extractor).
        Defines all configurable parameters for the template.
        
        STANDARD FORMAT: {properties: {...}, required: [...]}
        """
        return {
            "type": "object",
            "properties": {
                "use_custom_cidr": {
                    "type": "boolean",
                    "default": False,
                    "title": "Use Custom CIDR",
                    "description": "Enable to specify a custom IPv4 CIDR block for the VPC",
                    "order": 10,
                    "group": "Network Configuration",
                    "cost_impact": "$0/month"
                },
                "custom_cidr_block": {
                    "type": "string",
                    "default": "10.0.0.0/16",
                    "title": "Custom CIDR Block",
                    "description": "Specify custom IPv4 CIDR block (e.g., 10.0.0.0/16, 172.16.0.0/16, 192.168.0.0/16)",
                    "order": 11,
                    "group": "Network Configuration",
                    "conditional": {
                        "field": "use_custom_cidr"
                    }
                },
                "enable_dns_support": {
                    "type": "boolean",
                    "default": True,
                    "title": "Enable DNS Support",
                    "description": "Enable DNS resolution in the VPC",
                    "order": 12,
                    "group": "Network Configuration"
                },
                "enable_dns_hostnames": {
                    "type": "boolean",
                    "default": True,
                    "title": "Enable DNS Hostnames",
                    "description": "Enable DNS hostnames for instances",
                    "order": 13,
                    "group": "Network Configuration"
                },
                "enable_ssh_access": {
                    "type": "boolean",
                    "default": False,
                    "title": "Enable SSH Security Group",
                    "description": "Traditional SSH/RDP key-based access (alternative to SSM Session Manager)",
                    "architecture_decision": True,
                    "smart_default_enabled": False,
                    "foundation": True,
                    "section": "Security & Access",
                    "order": 102,
                    "group": "Architecture Decisions",
                    "cost_impact": "+$0/month"
                },
                "ssh_access_ip": {
                    "type": "string",
                    "default": "1.2.3.4/32",
                    "title": "SSH Access IP/CIDR",
                    "description": "IP address or CIDR block for SSH/RDP access (e.g., 203.0.113.45/32)",
                    "order": 15,
                    "group": "Network Configuration",
                    "conditional": {
                        "field": "enable_ssh_access"
                    }
                },
                "enable_nat_gateway": {
                    "type": "boolean",
                    "default": True,
                    "title": "Enable NAT Gateway",
                    "description": "Provides outbound internet access for private subnets via NAT Gateway",
                    "architecture_decision": True,
                    "smart_default_enabled": True,
                    "foundation": True,
                    "section": "Internet Access",
                    "order": 101,
                    "group": "Architecture Decisions",
                    "cost_impact": "+$32/month"
                },
                "enable_isolated_tier": {
                    "type": "boolean",
                    "default": False,
                    "title": "Enable Isolated Tier",
                    "description": "Additional database subnet tier with no internet access for maximum security",
                    "architecture_decision": True,
                    "smart_default_enabled": False,
                    "foundation": True,
                    "section": "Network Segmentation",
                    "order": 103,
                    "group": "Architecture Decisions",
                    "cost_impact": "+$0/month"
                },
                "enable_flow_logs": {
                    "type": "boolean",
                    "default": True,
                    "title": "Enable VPC Flow Logs",
                    "description": "S3-based network traffic capture for monitoring and troubleshooting (7-day retention)",
                    "architecture_decision": True,
                    "smart_default_enabled": True,
                    "foundation": True,
                    "section": "Monitoring & Security",
                    "order": 104,
                    "group": "Architecture Decisions",
                    "cost_impact": "+$3/month"
                },
                "flow_log_retention": {
                    "type": "integer",
                    "default": 7,
                    "title": "Flow Logs Retention (days)",
                    "description": "How long to retain flow logs in S3 before auto-deletion",
                    "order": 105,
                    "group": "High Availability & Cost"
                },
                "enable_rds_endpoint": {
                    "type": "boolean",
                    "default": False,
                    "title": "Enable RDS VPC Endpoint",
                    "description": "Private interface endpoint for secure RDS API access without traversing internet",
                    "architecture_decision": True,
                    "smart_default_enabled": False,
                    "foundation": False,
                    "section": "VPC Endpoints",
                    "order": 105,
                    "group": "Architecture Decisions",
                    "cost_impact": "+$14/month"
                },
                "enable_ssm_endpoints": {
                    "type": "boolean",
                    "default": False,
                    "title": "Enable SSM VPC Endpoints",
                    "description": "Private endpoints for AWS Systems Manager Session Manager (secure shell access alternative)",
                    "architecture_decision": True,
                    "smart_default_enabled": False,
                    "foundation": False,
                    "section": "VPC Endpoints",
                    "order": 106,
                    "group": "Architecture Decisions",
                    "cost_impact": "+$42/month"
                }
            },
            "required": ["project_name", "region"]
        }
