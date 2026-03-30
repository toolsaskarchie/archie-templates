# Estimated monthly cost: ~$20-24/mo (us-east-1) - IPv6 support adds ~$4/mo for dual-stack subnets
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
- IPv6 support (+$4/mo for dual-stack networking)
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
        self.egw: Optional[aws.ec2.EgressOnlyInternetGateway] = None
        self.nat_gateway: Optional[aws.ec2.NatGateway] = None
        self.subnets = {}
        self.route_tables = {}
        self.security_groups = {}
        self.vpc_endpoints = {}
        self.flow_logs_bucket: Optional[aws.s3.Bucket] = None
        self.flow_log: Optional[aws.ec2.FlowLog] = None
    
    def create_infrastructure(self) -> Dict[str, Any]:
        # Config values nested in parameters — check both levels (Rule #6)
        params = self.config.get('parameters', {})
        def cfg(key, default=None):
            return self.config.get(key) or params.get(key) or default

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
        
        # Reuse existing CIDR from outputs on upgrade, or use custom, or generate random
        params = self.config.get('parameters', {}) if isinstance(self.config, dict) else {}
        existing_cidr = cfg('vpc_cidr') or params.get('vpc_cidr') or cfg('cidr_block') or params.get('cidr_block')
        use_custom = self.cfg.get('use_custom_cidr', False)
        if existing_cidr and isinstance(existing_cidr, str) and '/' in existing_cidr:
            vpc_cidr = existing_cidr
            print(f"[VPC TEMPLATE] Reusing existing VPC CIDR: {vpc_cidr}")
        elif use_custom and self.cfg.get('custom_cidr_block'):
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
        
        # IPv6 support configuration
        enable_ipv6 = self.cfg.get('enable_ipv6', False)
        
        # =================================================================
        # LAYER 1: VPC Core
        # =================================================================
        
        vpc_name = self.cfg.get('vpc_name') or namer.vpc(cidr=vpc_cidr)
        vpc_args = {
            "cidr_block": vpc_cidr,
            "enable_dns_support": self._to_bool(self.config.get('enable_dns_support', self.config.get('parameters', {}).get('enable_dns_support', True))),
            "enable_dns_hostnames": self._to_bool(self.config.get('enable_dns_hostnames', self.config.get('parameters', {}).get('enable_dns_hostnames', True))),
            "instance_tenancy": self.cfg.instance_tenancy,
            "tags": {**tags, "Name": vpc_name}
        }
        
        # Add IPv6 support if enabled
        if enable_ipv6:
            vpc_args["assign_generated_ipv6_cidr_block"] = True
        
        self.vpc = factory.create("aws:ec2:Vpc", vpc_name, **vpc_args)
        
        vpc_id = self.vpc.id
        
        # =================================================================
        # LAYER 2: Internet Gateway and Egress-Only Gateway
        # =================================================================
        
        igw_name = namer.internet_gateway()
        self.igw = factory.create(
            "aws:ec2:InternetGateway",
            igw_name,
            vpc_id=vpc_id,
            tags={**tags, "Name": igw_name}
        )
        
        igw_id = self.igw.id
        
        # Create Egress-Only Internet Gateway for IPv6 if enabled
        if enable_ipv6:
            egw_name = namer.resource("egw")
            self.egw = factory.create(
                "aws:ec2:EgressOnlyInternetGateway",
                egw_name,
                vpc_id=vpc_id,
                tags={**tags, "Name": egw_name}
            )
        
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
        
        # Web Tier Security Group
        web_sg_name = namer.security_group("web", ports=[80, 443])
        web_ingress_rules = [
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
        ]
        
        # Add IPv6 rules if enabled
        if enable_ipv6:
            web_ingress_rules.extend([
                {
                    "protocol": "tcp",
                    "from_port": 80,
                    "to_port": 80,
                    "ipv6_cidr_blocks": ["::/0"],
                    "description": "HTTP from internet (IPv6)"
                },
                {
                    "protocol": "tcp",
                    "from_port": 443,
                    "to_port": 443,
                    "ipv6_cidr_blocks": ["::/0"],
                    "description": "HTTPS from internet (IPv6)"
                }
            ])
        
        self.security_groups['web'] = factory.create(
            "aws:ec2:SecurityGroup",
            web_sg_name,
            vpc_id=vpc_id,
            description="Security group for web tier (HTTP/HTTPS)",
            ingress=web_ingress_rules,
            egress=[
                {
                    "protocol": "-1",
                    "from_port": 0,
                    "to_port": 0,
                    "cidr_blocks": ["0.0.0.0/0"],
                    "description": "Allow all outbound"
                }
            ] + ([
                {
                    "protocol": "-1",
                    "from_port": 0,
                    "to_port": 0,
                    "ipv6_cidr_blocks": ["::/0"],
                    "description": "Allow all outbound (IPv6)"
                }
            ] if enable_ipv6 else []),
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
            ] + ([
                {
                    "protocol": "-1",
                    "from_port": 0,
                    "to_port": 0,
                    "ipv6_cidr_blocks": ["::/0"],
                    "description": "Allow all outbound (IPv6)"
                }
            ] if enable_ipv6 else []),
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
            ] + ([
                {
                    "protocol": "-1",
                    "from_port": 0,
                    "to_port": 0,
                    "ipv6_cidr_blocks": ["::/0"],
                    "description": "Allow all outbound (IPv6)"
                }
            ] if enable_ipv6 else []),
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
                ] + ([
                    {
                        "protocol": "-1",
                        "from_port": 0,
                        "to_port": 0,
                        "ipv6_cidr_blocks": ["::/0"],
                        "description": "Allow all outbound (IPv6)"
                    }
                ] if enable_ipv6 else []),
                tags={**tags, "Name": access_sg_name, "Tier": "management"}
            )
        
        # =================================================================
        # LAYER 6: Subnets (Single AZ)
        # =================================================================
        
        az = self.cfg.az_1 or f"{self.cfg.region}a"
        
        # Public Subnet
        public_subnet_name = namer.subnet("public", az, cidr=public_cidr)
        public_subnet_args = {
            "vpc_id": vpc_id,
            "cidr_block": public_cidr,
            "availability_zone": az,
            "map_public_ip_on_launch": True,
            "tags": {**tags, "Name": public_subnet_name, "Tier": "public"}
        }
        
        # Add IPv6 configuration if enabled
        if enable_ipv6:
            # IPv6 CIDR block will be assigned automatically from VPC's IPv6 CIDR
            public_subnet_args["assign_ipv6_address_on_creation"] = True
            public_subnet_args["ipv6_cidr_block"] = self.vpc.ipv6_cidr_block.apply(
                lambda cidr: f"{cidr[:-2]}00/64" if cidr else None
            )
        
        self.subnets['public'] = factory.create("aws:ec2:Subnet", public_subnet_name, **public_subnet_args)

        # Private Subnet
        private_subnet_name = namer.subnet("private", az, cidr=private_cidr)
        private_subnet_args = {
            "vpc_id": vpc_id,
            "cidr_block": private_cidr,
            "availability_zone": az,
            "map_public_ip_on_launch": False,
            "tags": {**tags, "Name": private_subnet_name, "Tier": "private"}
        }
        
        if enable_ipv6:
            private_subnet_args["assign_ipv6_address_on_creation"] = False
            private_subnet_args["ipv6_cidr_block"] = self.vpc.ipv6_cidr_block.apply(
                lambda cidr: f"{cidr[:-2]}01/64" if cidr else None
            )
        
        self.subnets['private'] = factory.create("aws:ec2:Subnet", private_subnet_name, **private_subnet_args)

        # Isolated Subnet (conditional)
        if self.cfg.enable_isolated_tier:
            isolated_subnet_name = namer.subnet("isolated", az, cidr=isolated_cidr)
            isolated_subnet_args = {
                "vpc_id": vpc_id,
                "cidr_block": isolated_cidr,
                "availability_zone": az,
                "map_public_ip_on_launch": False,
                "tags": {**tags, "Name": isolated_subnet_name, "Tier": "isolated"}
            }
            
            if enable_ipv6:
                isolated_subnet_args["assign_ipv6_address_on_creation"] = False
                isolated_subnet_args["ipv6_cidr_block"] = self.vpc.ipv6_cidr_block.apply(
                    lambda cidr: f"{cidr[:-2]}02/64" if cidr else None
                )
            
            self.subnets['isolated'] = factory.create("aws:ec2:Subnet", isolated_subnet_name, **isolated_subnet_args)
        
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
        
        # Public route to IGW (IPv4)
        public_route_name = namer.route("0.0.0.0/0", "igw")
        factory.create(
            "aws:ec2:Route",
            public_route_name,
            route_table_id=self.route_tables['public'].id,
            destination_cidr_block="0.0.0.0/0",
            gateway_id=igw_id
        )
        
        # Public route to IGW (IPv6) if enabled
        if enable_ipv6:
            public_route_ipv6_name = namer.route("::/0", "igw")
            factory.create(
                "aws:ec2:Route",
                public_route_ipv6_name,
                route_table_id=self.route_tables['public'].id,
                destination_ipv6_cidr_block="::/0",
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
        
        # Private IPv6 egress route if enabled
        if enable_ipv6 and self.egw:
            private_route_ipv6_name = namer.route("::/0", "egw")
            factory.create(
                "aws:ec2:Route",
                private_route_ipv6_name,
                route_table_id=self.route_tables['private'].id,
                destination_ipv6_cidr_block="::/0",
                egress_only_gateway_id=self.egw.id
            )
        
        # Isolated tier IPv6 egress route if enabled
        if self.cfg.enable_isolated_tier and enable_ipv6 and self.egw:
            isolated_route_ipv6_name = namer.route("::/0", "egw-isolated")
            factory.create(
                "aws:ec2:Route",
                isolated_route_ipv6_name,
                route_table_id=self.route_tables['isolated'].id,
                destination_ipv6_cidr_block="::/0",
                egress_only_gateway_id=self.egw.id
            )
        
        # No IPv4 route for isolated tier - VPC-only traffic
        
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
                tags={**tags, "Name": bucket_name, "Purpose": "VPC Flow Logs