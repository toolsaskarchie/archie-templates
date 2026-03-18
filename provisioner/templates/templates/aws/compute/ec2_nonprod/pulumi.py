from typing import Any, Dict, Optional, List
import json
import pulumi
import pulumi_aws as aws

from provisioner.templates.base import InfrastructureTemplate, template_registry
from provisioner.utils.aws import get_standard_tags, ResourceNamer
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory
from provisioner.templates.templates.aws.compute.ec2_nonprod.config import EC2NonProdConfig
from provisioner.templates.templates.aws.networking.vpc_nonprod.pulumi import VPCSimpleNonprodTemplate

@template_registry("aws-ec2-nonprod")
class EC2NonProdTemplate(InfrastructureTemplate):
    """
    EC2 Non-Production Instance - Pattern B
    
    Creates:
    - VPC (if new)
    - IAM Role & Instance Profile
    - Security Groups
    - EC2 Instance(s)
    """
    def __init__(self, name: str = None, config: Dict[str, Any] = None, **kwargs):
        raw_config = config or kwargs or {}
        if name is None:
            name = raw_config.get('instanceName', 'ec2-nonprod')
        super().__init__(name, raw_config)
        self.cfg = EC2NonProdConfig(raw_config)
        
        # Resource references
        self.vpc_template: Optional[VPCSimpleNonprodTemplate] = None
        self.iam_roles = []
        self.instance_profiles = []
        self.security_groups = []
        self.ec2_instances = []
        
    def create_infrastructure(self) -> Dict[str, Any]:
        return self.create()

    def create(self) -> Dict[str, Any]:
        """Deploy infrastructure using Pattern B"""
        # VPC Mode Resolution
        vpc_mode = self.cfg.vpc_mode
        if isinstance(vpc_mode, str) and '(' in vpc_mode:
            vpc_mode = vpc_mode.split('(')[0].strip()
        
        # Initialize Namer
        namer = ResourceNamer(
            project=self.cfg.project_name,
            environment=self.cfg.environment,
            region=self.cfg.region,
            template="ec2-nonprod"
        )
        
        # Instance Name Resolution
        instance_name = self.cfg.instance_name
        if not instance_name or instance_name.lower() == 'auto-assign':
            preset_name = self.cfg.config_preset if self.cfg.config_preset != 'custom' else "instance"
            instance_name = namer.ec2_instance(preset=preset_name)
        
        if isinstance(instance_name, str) and '(' in instance_name:
            instance_name = instance_name.split('(')[0].strip()

        # Get preset for naming
        preset_for_naming = self.cfg.config_preset if self.cfg.config_preset and self.cfg.config_preset != 'custom' else "instance"
        if hasattr(self.cfg, 'application_preset') and self.cfg.application_preset:
            preset_map = {"Web Server": "web", "Database Server": "db", "Cache Server": "cache", "Custom": "instance"}
            preset_for_naming = preset_map.get(self.cfg.application_preset, "instance")

        tags = namer.tags()
        
        # Resolve AMI
        ami_id = self.cfg.ami_id
        if isinstance(ami_id, str) and '(' in ami_id:
            ami_id = ami_id.split('(')[0].strip()
        ami_os = self.cfg.ami_os
        
        if ami_id.startswith('resolve-ssm:'):
            owners = []
            filters = []
            if ami_os == 'amazon-linux-2':
                owners = ["amazon"]
                filters = [aws.ec2.GetAmiFilterArgs(name="name", values=["amzn2-ami-hvm-*-x86_64-gp2"])]
            elif ami_os == 'ubuntu-22.04':
                owners = ["099720109477"]  # Canonical
                filters = [aws.ec2.GetAmiFilterArgs(name="name", values=["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"])]
            elif ami_os == 'windows-2022':
                owners = ["amazon"]
                filters = [aws.ec2.GetAmiFilterArgs(name="name", values=["Windows_Server-2022-English-Full-Base-*"])]
            
            if filters:
                filters.append(aws.ec2.GetAmiFilterArgs(name="state", values=["available"]))
                ami = aws.ec2.get_ami(most_recent=True, owners=owners, filters=filters)
                ami_id = ami.id

        # Networking Logic
        vpc_app_sg = None
        vpc_web_sg = None
        vpc_db_sg = None
        base_security_groups = []
        
        if vpc_mode == 'new':
            print(f"[EC2] Calling VPC template for instance '{instance_name}'")
            
            # Resolve VPC CIDR
            if self.cfg.use_custom_cidr:
                vpc_cidr = self.cfg.cidr_block
                # Strip description text from vpc_cidr
                vpc_cidr = vpc_cidr.split('(')[0].strip() if isinstance(vpc_cidr, str) and '(' in vpc_cidr else vpc_cidr
            else:
                vpc_cidr = 'random'
            vpc_cidr = self.cfg.cidr_block or generate_random_vpc_cidr()
            
            vpc_config = {
                "parameters": {
                    "aws": {
                        "project_name": self.cfg.project_name,
                        "cidr_block": vpc_cidr,
                        "environment": self.cfg.environment,
                        "vpc_name": self.cfg.vpc_name,
                        "enable_nat_gateway": self.cfg.enable_nat_gateway,
                        "enable_ssm_endpoints": self.cfg.enable_ssm_endpoints,
                        "enable_s3_endpoint": self.cfg.enable_s3_endpoint,
                        "enable_dynamodb_endpoint": self.cfg.enable_dynamodb_endpoint
                    }
                }
            }

            self.vpc_template = VPCSimpleNonprodTemplate(name=f"{self.name}-vpc", config=vpc_config)
            self.vpc_template.create_infrastructure()
            vpc_outputs = self.vpc_template.get_outputs()
            
            vpc_id = vpc_outputs['vpc_id']
            subnet_id = (vpc_outputs.get('public_subnet_ids') or [vpc_outputs.get('public_subnet_id')])[0]
            
            vpc_app_sg = vpc_outputs.get('app_security_group_id')
            vpc_web_sg = vpc_outputs.get('web_security_group_id')
            vpc_db_sg = vpc_outputs.get('db_security_group_id')
            
            if self.cfg.ssh_access_ip and 'access_security_group_id' in vpc_outputs:
                access_sg_id = vpc_outputs['access_security_group_id']
                base_security_groups.append(access_sg_id)
                
                remote_port = 3389 if ami_os == 'windows-2022' else 22
                remote_proto = "RDP" if ami_os == 'windows-2022' else "SSH"
                
                allowed_ips = [self.cfg.ssh_access_ip] if isinstance(self.cfg.ssh_access_ip, str) else self.cfg.ssh_access_ip
                for idx, ip in enumerate(allowed_ips):
                    cidr_ip = ip if '/' in ip else f"{ip}/32"
                    factory.create(
                        "aws:ec2:SecurityGroupRule",
                        f"{self.name}-{remote_proto.lower()}-rule-{idx}",
                        type="ingress",
                        security_group_id=access_sg_id,
                        protocol="tcp",
                        from_port=remote_port,
                        to_port=remote_port,
                        cidr_blocks=[cidr_ip],
                        description=f"{remote_proto} from {cidr_ip}"
                    )
        else:
            vpc_id = self.cfg.vpc_id
            subnet_id = self.cfg.subnet_id
            
            if self.cfg.ssh_access_ip:
                remote_port = 3389 if ami_os == 'windows-2022' else 22
                remote_proto = "RDP" if ami_os == 'windows-2022' else "SSH"
                
                access_sg_ingress = []
                allowed_ips = [self.cfg.ssh_access_ip] if isinstance(self.cfg.ssh_access_ip, str) else self.cfg.ssh_access_ip
                for ip in allowed_ips:
                    cidr_ip = ip if '/' in ip else f"{ip}/32"
                    access_sg_ingress.append({
                        "protocol": "tcp",
                        "from_port": remote_port,
                        "to_port": remote_port,
                        "cidr_blocks": [cidr_ip],
                        "description": f"{remote_proto} from {cidr_ip}"
                    })
                
                access_sg_name = namer.security_group(purpose="access")
                access_sg = factory.create(
                    "aws:ec2:SecurityGroup",
                    access_sg_name,
                    vpc_id=vpc_id,
                    description="Management access",
                    ingress=access_sg_ingress,
                    egress=[{"protocol": "-1", "from_port": 0, "to_port": 0, "cidr_blocks": ["0.0.0.0/0"]}],
                    tags={**tags, "Name": access_sg_name}
                )
                self.security_groups.append(access_sg)
                base_security_groups.append(access_sg.id)
            
            # SG Discovery
            def discover_sgs(v_id):
                import boto3
                try:
                    ec2 = boto3.client('ec2', region_name=self.cfg.region)
                    filters = [
                        {"name": "vpc-id", "values": [v_id]},
                        {"name": "tag:Project", "values": [self.cfg.project_name]}
                    ]
                    found = {}
                    for tier in ['web', 'app', 'db']:
                        f = filters + [{"name": "tag:Tier", "values": [tier]}]
                        resp = ec2.describe_security_groups(Filters=f)
                        if resp['SecurityGroups']:
                            found[tier] = resp['SecurityGroups'][0]['GroupId']
                    return found
                except: return {}

            discovery = pulumi.Output.from_input(vpc_id).apply(discover_sgs)
            vpc_app_sg = discovery.apply(lambda s: s.get('app'))
            vpc_web_sg = discovery.apply(lambda s: s.get('web'))
            vpc_db_sg = discovery.apply(lambda s: s.get('db'))

        # IAM & Instances
        instance_profile_name = None
        if self.cfg.enable_ssm:
            role_name = namer.iam_role("ec2", preset_for_naming)
            iam_role = factory.create(
                "aws:iam:Role",
                role_name,
                assume_role_policy=json.dumps({
                    "Version": "2012-10-17",
                    "Statement": [{"Effect": "Allow", "Principal": {"Service": "ec2.amazonaws.com"}, "Action": "sts:AssumeRole"}]
                }),
                managed_policy_arns=["arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"],
                tags={**tags, "Name": role_name}
            )
            self.iam_roles.append(iam_role)
            
            profile_name = namer.iam_profile("ec2", preset_for_naming)
            instance_profile = factory.create(
                "aws:iam:InstanceProfile",
                profile_name,
                role=iam_role.name,
                tags={**tags, "Name": profile_name}
            )
            self.instance_profiles.append(instance_profile)
            instance_profile_name = instance_profile.name

        # Create Instances
        for idx in range(1, self.cfg.instance_count + 1):
            name_final = namer.ec2_instance(preset_for_naming, sequence=idx if self.cfg.instance_count > 1 else None)
            sgs = [s for s in base_security_groups + (self.cfg.security_group_ids or []) if s]
            # Assign the right SG tier based on preset
            preset_sg_map = {"web-server": vpc_web_sg, "alb-backend": vpc_app_sg, "mysql": vpc_db_sg, "wordpress": vpc_web_sg}
            tier_sg = preset_sg_map.get(self.cfg.config_preset, vpc_app_sg)
            if tier_sg: sgs.append(tier_sg)

            # Filter out None values from Pulumi Outputs at runtime
            resolved_sgs = pulumi.Output.all(*sgs).apply(lambda ids: [i for i in ids if i])

            inst = factory.create(
                "aws:ec2:Instance",
                name_final,
                instance_type=self.cfg.instance_type,
                ami=ami_id,
                subnet_id=subnet_id,
                vpc_security_group_ids=resolved_sgs,
                iam_instance_profile=instance_profile_name,
                key_name=self.cfg.key_name,
                user_data=self.cfg.user_data,
                tags={**tags, "Name": name_final, "ManagedBy": "Archie"}
            )
            self.ec2_instances.append(inst)

        # Pulumi exports for stack outputs
        first_ec2 = self.ec2_instances[0]
        pulumi.export("instance_id", first_ec2.id)
        pulumi.export("instance_type", self.cfg.instance_type)
        pulumi.export("public_ip", first_ec2.public_ip)
        pulumi.export("private_ip", first_ec2.private_ip)
        pulumi.export("security_group_id", first_ec2.vpc_security_group_ids)
        if self.vpc_template:
            vpc_out = self.vpc_template.get_outputs()
            pulumi.export("vpc_id", vpc_out.get("vpc_id"))
            pulumi.export("subnet_id", vpc_out.get("public_subnet_id"))
        pulumi.export("ssh_command", first_ec2.public_ip.apply(
            lambda ip: f"ssh -i key.pem ec2-user@{ip}" if ip else "N/A (no public IP)"
        ))

        return self.get_outputs()
    
    def get_outputs(self) -> Dict[str, Any]:
        """Get template outputs"""
        if not self.ec2_instances:
            return {
                "instance_name": self.cfg.instance_name,
                "instance_type": self.cfg.instance_type,
                "status": "not_created"
            }
        
        # Get outputs from first EC2 instance (for backward compatibility)
        first_ec2 = self.ec2_instances[0]
        
        outputs = {
            "instance_id": first_ec2.id,
            "instance_name": self.cfg.instance_name,
            "instance_type": self.cfg.instance_type,
            "private_ip": first_ec2.private_ip,
        }
        
        # Add public IP if instance has one
        outputs["public_ip"] = first_ec2.public_ip
        
        # Add VPC info if we created it via template
        if self.vpc_template:
            vpc_outputs = self.vpc_template.get_outputs()
            outputs["vpc_id"] = vpc_outputs.get("vpc_id")
            outputs["vpc_cidr"] = vpc_outputs.get("vpc_cidr")
            # Include VPC security groups so they appear in resources list
            outputs["vpc_default_sg_id"] = vpc_outputs.get("default_security_group_id")
            outputs["vpc_app_sg_id"] = vpc_outputs.get("app_security_group_id")
            outputs["vpc_db_sg_id"] = vpc_outputs.get("db_security_group_id")
            # Add subnet info
            # Add subnet info
            outputs["public_subnet_ids"] = vpc_outputs.get("public_subnet_ids")
            if outputs["public_subnet_ids"] is None and "public_subnet_id" in vpc_outputs:
                outputs["public_subnet_ids"] = [vpc_outputs["public_subnet_id"]]
                
            outputs["private_subnet_ids"] = vpc_outputs.get("private_subnet_ids")
            if outputs["private_subnet_ids"] is None and "private_subnet_id" in vpc_outputs:
                outputs["private_subnet_ids"] = [vpc_outputs["private_subnet_id"]]
        
        # Add IAM role info if we created it
        if self.iam_roles:
            iam_role = self.iam_roles[0]
            outputs["iam_role_arn"] = iam_role.arn
            outputs["iam_role_name"] = iam_role.name
        
        # Add IAM instance profile info if we created it
        if self.instance_profiles:
            profile = self.instance_profiles[0]
            outputs["iam_instance_profile_arn"] = profile.arn
            outputs["iam_instance_profile_name"] = profile.name
        
        # Add SSH security group info (if created)
        if self.security_groups:
            # The first security group created is typically the SSH/Access SG
            sg = self.security_groups[0]
            outputs["ssh_security_group_id"] = sg.id
        
        return outputs
    
    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        """
        Get configuration schema for the UI - ALL IN PULUMI
        
        CRITICAL: Config fields MUST have cost_impact for frontend to show them!
        Frontend filters out fields without costWhenEnabled.
        """
        return {
            "application_preset": {
                "type": "string",
                "default": "Web Server",
                "title": "Application Preset",
                "description": "Pre-configured application template with optimized instance type and security groups",
                "order": 10,
                "group": "Compute Configuration",
                "resource_category": "Instance",
                "enum": ["Web Server", "Database Server", "Cache Server", "Custom"],
                "cost_impact": "$0/month (preset selection, actual cost varies by instance type)"
            },
            "instance_type": {
                "type": "string",
                "default": "t3.micro",
                "title": "Instance Type",
                "description": "EC2 instance type (t3.micro = $7.30/mo, t3.small = $14.60/mo, t3.medium = $29.20/mo)",
                "order": 11,
                "group": "Compute Configuration",
                "enum": ["t3.micro", "t3.small", "t3.medium", "t3.large"],
                "cost_impact": "$7-60/month depending on instance type"
            },
            "ami_os": {
                "type": "string",
                "default": "amazon-linux-2",
                "title": "Operating System",
                "description": "Operating system for the EC2 instance",
                "order": 12,
                "group": "Compute Configuration",
                "enum": ["amazon-linux-2", "ubuntu-22.04", "windows-2022"],
                "cost_impact": "$0/month (OS choice, actual cost in instance type)"
            },
            "instance_count": {
                "type": "integer",
                "default": 1,
                "title": "Number of Instances",
                "description": "Number of EC2 instances to create (1-5)",
                "order": 13,
                "group": "Compute Configuration",
                "resource_category": "Instance",
                "enum": [1, 2, 3, 4, 5],
                "cost_impact": "Multiplies instance cost by count"
            },
            "vpc_mode": {
                "type": "string",
                "default": "new",
                "title": "VPC Mode",
                "description": "Create new VPC infrastructure or use existing VPC",
                "order": 20,
                "group": "Network Configuration",
                "enum": ["new", "existing"],
                "cost_impact": "$0/month (mode selection, VPC components have separate costs)"
            },
            "use_custom_cidr": {
                "type": "boolean",
                "default": False,
                "title": "Use Custom CIDR",
                "description": "Enable to specify a custom IPv4 CIDR block for the new VPC",
                "order": 20.1,
                "group": "Network Configuration",
                "resource_category": "Vpc",
                "cost_impact": "$0/month"
            },
            "cidr_block": {
                "type": "string",
                "default": "random",
                "title": "VPC CIDR Block",
                "description": "IPv4 CIDR block for new VPC (only if vpc_mode=new)",
                "order": 21,
                "group": "Network Configuration",
                "resource_category": "Vpc",
                "cost_impact": "$0/month (CIDR selection is free)",
                "conditional": {
                    "field": "use_custom_cidr"
                }
            },
            "enable_nat_gateway": {
                "type": "boolean",
                "default": True,
                "title": "Enable NAT Gateway",
                "description": "Provides internet access for private subnets (required for private instance internet access)",
                "order": 22,
                "group": "Network Configuration",
                "resource_category": "Vpc",
                "cost_impact": "+$32/month ($0.045/hour + data transfer)"
            },
            "enable_flow_logs": {
                "type": "boolean",
                "default": True,
                "title": "Enable VPC Flow Logs",
                "description": "Capture network traffic logs for security and troubleshooting (stored in S3)",
                "order": 23,
                "group": "Network Configuration",
                "resource_category": "Vpc",
                "cost_impact": "+$3/month (S3 storage + processing)"
            },
            "enable_s3_endpoint": {
                "type": "boolean",
                "default": True,
                "title": "Enable S3 VPC Endpoint",
                "description": "Free gateway endpoint for private S3 access (no internet traffic, no data transfer charges)",
                "order": 24,
                "group": "Network Configuration",
                "resource_category": "Vpc",
                "cost_impact": "$0/month (gateway endpoint is free)"
            },
            "enable_dynamodb_endpoint": {
                "type": "boolean",
                "default": True,
                "title": "Enable DynamoDB VPC Endpoint",
                "description": "Free gateway endpoint for private DynamoDB access",
                "order": 25,
                "group": "Network Configuration",
                "resource_category": "Vpc",
                "cost_impact": "$0/month (gateway endpoint is free)"
            },
            "enable_ssm": {
                "type": "boolean",
                "default": True,
                "title": "Enable AWS Systems Manager",
                "description": "Secure instance access without SSH keys via AWS Systems Manager Session Manager",
                "order": 100,
                "group": "Security & Access",
                "cost_impact": "$0/month (SSM Session Manager is free, creates IAM role/profile)"
            },
            "enable_ssm_endpoints": {
                "type": "boolean",
                "default": False,
                "title": "Enable SSM VPC Endpoints",
                "description": "Private endpoints for SSM in isolated subnets without internet access (3 endpoints: ssm, ssmmessages, ec2messages)",
                "order": 101,
                "group": "Security & Access",
                "resource_category": "Vpc",
                "cost_impact": "+$21/month (3 endpoints × $7/mo each)"
            },
            "enable_ssh_access": {
                "type": "boolean",
                "default": False,
                "title": "Enable SSH Access",
                "description": "Create a security group for direct SSH/RDP access from your IP",
                "order": 105,
                "group": "Security & Access",
                "resource_category": "SecurityGroup",
                "cost_impact": "$0/month"
            },
            "ssh_access_ip": {
                "type": "string",
                "default": "",
                "title": "Admin Access IP (SSH/RDP)",
                "description": "Your public IP address to restrict management access.",
                "placeholder": "1.2.3.4/32",
                "order": 106,
                "group": "Security & Access",
                "resource_category": "SecurityGroup",
                "help_text": "Archie recommends SSM by default, additionally or if you prefer SSH - Enter your public IP for direct access.",
                "cost_impact": "$0/month",
                "conditional": {
                    "field": "enable_ssh_access"
                }
            }
        }

    @classmethod
    def get_metadata(cls):
        """Get template metadata"""
        from provisioner.templates.base.template import TemplateMetadata, TemplateCategory
        return {
            "name": "aws-ec2-nonprod",
            "title": "Flexible EC2 Development Instance",
            "description": "Complete cost-optimized EC2 infrastructure for development, staging, and testing environments. Choose between creating a new VPC with full networking setup (subnets, internet gateway, NAT gateway, route tables, security groups) or deploying into an existing VPC. Includes EC2 instance with IAM role/profile, multiple application presets (Web Server, WordPress, MySQL, Node.js, ALB Backend, Custom), pre-configured security groups for SSH access, application traffic, database connections, and web services. Features VPC endpoints for S3 and DynamoDB, VPC Flow Logs for monitoring, and AWS Systems Manager (SSM) integration for secure instance management without SSH keys. Supports both public and private subnet deployments with optional NAT gateway for private subnet internet access. Automatically assigns appropriate security groups based on application preset (web presets get HTTP/HTTPS access, database presets get app security groups). Creates IAM roles with SSM managed policies and S3 read access for static assets. Exports instance details, IP addresses, VPC information, and connection commands for SSH and SSM access.",
            "category": "compute",
            "version": "1.2.0",
            "author": "InnovativeApps",
            "base_template": "aws-vpc-nonprod",
            "tags": ["ec2", "compute", "development", "nonprod", "cost-optimized"],
            "use_cases": [
                {
                    "title": "Development & Testing Workloads",
                    "description": "Deploy isolated EC2 instances for application development, QA testing, and staging environments with cost-effective instance types."
                },
                {
                    "title": "Web Application Hosting",
                    "description": "Host web servers, WordPress sites, or Node.js applications with pre-configured security groups and application presets."
                },
                {
                    "title": "Database Development Instances",
                    "description": "Run MySQL, PostgreSQL, or other database engines for development and testing with appropriate security controls."
                },
                {
                    "title": "CI/CD Build Agents",
                    "description": "Deploy dedicated build agents or Jenkins workers with SSM access and S3 integration for artifact storage."
                },
                {
                    "title": "Application Backend Services",
                    "description": "Run backend APIs and microservices behind Application Load Balancers with auto-configured security groups."
                }
            ],
            "features": [
                "Flexible VPC Integration (New/Existing VPC)",
                "Application/Stack Presets (Web, Node.js, DB)",
                "Cost-Effective t3-Family Instance Support",
                "Integrated Security Group presets for Common Ports",
                "Secure Access via SSH or AWS Systems Manager (SSM)",
                "S3 Integration for Static Assets & Deployment",
                "Multi-Instance Support with Custom Configurations",
                "Multiple AMI Options (Amazon Linux 2, Ubuntu, Windows)"
            ],
            "estimated_cost": "$10-35/month (Burstable performance)",
            "cloud": "aws",
            "complexity": "medium",
            "deployment_time": "5-8 minutes",
            "marketplace_group": "aws-compute-group",
            "is_listed_in_marketplace": True,
            "pillars": [
                {
                    "title": "Operational Excellence",
                    "score": 75,
                    "score_color": "#f59e0b",
                    "practices": [
                        "SSM integration enables secure, auditable instance access without managing SSH keys or bastion hosts",
                        "Application presets provide standardized configurations for common workloads (web servers, databases, Node.js)",
                        "VPC Flow Logs capture network traffic for troubleshooting and security analysis",
                        "User data scripts automate initial instance configuration and application deployment",
                        "CloudWatch integration through SSM agent provides centralized logging and monitoring"
                    ]
                },
                {
                    "title": "Security",
                    "score": 80,
                    "score_color": "#10b981",
                    "practices": [
                        "Security groups restrict access to only required ports based on application preset",
                        "IAM instance profiles follow least-privilege principle with SSM and S3 read-only access",
                        "VPC isolation options (public/private subnets) protect instances from direct internet exposure",
                        "SSH/RDP access limited to specified IP ranges with optional key pair authentication",
                        "SSM Session Manager provides encrypted, auditable shell access without exposing SSH ports",
                        "VPC endpoints enable private AWS service access without internet gateway traversal"
                    ]
                },
                {
                    "title": "Reliability",
                    "score": 65,
                    "score_color": "#f59e0b",
                    "practices": [
                        "Multi-AZ VPC architecture provides infrastructure redundancy for networking components",
                        "NAT gateway options ensure reliable outbound internet connectivity from private subnets",
                        "Instance status checks and automatic recovery can be enabled via AWS Systems Manager",
                        "Multiple availability zones supported for subnet placement",
                        "Note: Single-instance design suitable for dev/test; production workloads should use Auto Scaling Groups"
                    ]
                },
                {
                    "title": "Performance Efficiency",
                    "score": 70,
                    "score_color": "#f59e0b",
                    "practices": [
                        "T3 burstable instances provide cost-effective baseline performance with burst capacity",
                        "Application presets select appropriate instance types (t3.micro for web, t3.small for databases)",
                        "VPC endpoints reduce latency and data transfer costs for S3/DynamoDB access",
                        "Multiple AMI options (Amazon Linux 2, Ubuntu, Windows) optimized for different workloads",
                        "User data scripts enable rapid instance bootstrapping and application deployment"
                    ]
                },
                {
                    "title": "Cost Optimization",
                    "score": 85,
                    "score_color": "#10b981",
                    "practices": [
                        "T3 instance family provides lowest-cost option for variable workloads ($10-35/month)",
                        "Single-AZ VPC option eliminates unnecessary NAT gateway costs for dev environments",
                        "Optional NAT gateway deployment reduces costs when outbound internet not required",
                        "VPC endpoints eliminate data transfer charges for S3 and DynamoDB access",
                        "Burstable performance instances accumulate credits during idle periods for burst workloads",
                        "Flexible VPC modes allow using existing infrastructure to avoid duplication costs"
                    ]
                },
                {
                    "title": "Sustainability",
                    "score": 70,
                    "score_color": "#f59e0b",
                    "practices": [
                        "T3 instances use AWS Nitro System for improved resource efficiency and lower power consumption",
                        "Burstable instances reduce over-provisioning by rightsizing to actual workload needs",
                        "Single-instance nonprod design minimizes unnecessary resource consumption",
                        "Optional VPC creation prevents infrastructure duplication across projects",
                        "SSM enables instance management without additional bastion hosts or jump boxes"
                    ]
                }
            ]
        }
    
    @classmethod
    def get_diagram(cls) -> Dict[str, Any]:
        """Generate infrastructure diagram for Overview tab"""
        return {
            "title": "EC2 NonProd Infrastructure",
            "description": "Single EC2 instance with VPC, security groups, and IAM",
            "layout": "hierarchical",
            "nodes": [
                {
                    "id": "aws-account",
                    "type": "container",
                    "label": "AWS Account",
                    "icon": "cloud",
                    "style": {
                        "borderColor": "#FF9900",
                        "bgColor": "#FFF9F0"
                    },
                    "children": [
                        {
                            "id": "vpc",
                            "type": "container",
                            "label": "VPC",
                            "subLabel": "10.0.0.0/16 (2 AZs)",
                            "icon": "vpc",
                            "metadata": {
                                "cidr": "10.0.0.0/16",
                                "region": "us-east-1",
                                "azs": 2
                            },
                            "style": {
                                "borderColor": "#527FFF",
                                "bgColor": "#F0F4FF"
                            },
                            "children": [
                                {
                                    "id": "subnet-public-1",
                                    "type": "resource",
                                    "label": "Public Subnet 1",
                                    "subLabel": "10.0.1.0/24 (us-east-1a)",
                                    "icon": "subnet",
                                    "style": {
                                        "bgColor": "#E8F5E9",
                                        "borderColor": "#4CAF50"
                                    }
                                },
                                {
                                    "id": "subnet-private-1",
                                    "type": "resource",
                                    "label": "Private Subnet 1",
                                    "subLabel": "10.0.2.0/24 (us-east-1b)",
                                    "icon": "subnet",
                                    "style": {
                                        "bgColor": "#FFF3E0",
                                        "borderColor": "#FF9800"
                                    }
                                },
                                {
                                    "id": "igw",
                                    "type": "resource",
                                    "label": "Internet Gateway",
                                    "icon": "gateway",
                                    "style": {
                                        "bgColor": "#E3F2FD"
                                    }
                                },
                                {
                                    "id": "rt-public",
                                    "type": "resource",
                                    "label": "Public Route Table",
                                    "subLabel": "Routes to IGW",
                                    "icon": "route-table"
                                },
                                {
                                    "id": "rt-private",
                                    "type": "resource",
                                    "label": "Private Route Table",
                                    "subLabel": "Routes to NAT",
                                    "icon": "route-table"
                                }
                            ]
                        },
                        {
                            "id": "security-groups",
                            "type": "group",
                            "label": "Security Groups",
                            "icon": "shield",
                            "style": {
                                "borderColor": "#AB47BC",
                                "bgColor": "#F3E5F5"
                            },
                            "children": [
                                {
                                    "id": "sg-app",
                                    "type": "resource",
                                    "label": "App Security Group",
                                    "subLabel": "Ports: 80, 443",
                                    "icon": "security-group",
                                    "metadata": {
                                        "inbound": ["80/tcp (0.0.0.0/0)", "443/tcp (0.0.0.0/0)"],
                                        "outbound": ["all"]
                                    }
                                },
                                {
                                    "id": "sg-db",
                                    "type": "resource",
                                    "label": "DB Security Group",
                                    "subLabel": "Port: 3306",
                                    "icon": "security-group",
                                    "metadata": {
                                        "inbound": ["3306/tcp (VPC)"],
                                        "outbound": ["all"]
                                    }
                                },
                                {
                                    "id": "sg-default",
                                    "type": "resource",
                                    "label": "Default Security Group",
                                    "subLabel": "Custom rules",
                                    "icon": "security-group"
                                }
                            ]
                        },
                        {
                            "id": "iam",
                            "type": "group",
                            "label": "IAM Roles",
                            "icon": "key",
                            "style": {
                                "borderColor": "#FFB300",
                                "bgColor": "#FFF8E1"
                            },
                            "children": [
                                {
                                    "id": "iam-role",
                                    "type": "resource",
                                    "label": "EC2 Instance Profile",
                                    "subLabel": "SSM Managed Core",
                                    "icon": "iam-role",
                                    "metadata": {
                                        "policies": ["AmazonSSMManagedInstanceCore"]
                                    }
                                }
                            ]
                        },
                        {
                            "id": "ec2-instance",
                            "type": "resource",
                            "label": "EC2 Instance",
                            "subLabel": "t3.micro - Amazon Linux 2",
                            "icon": "ec2",
                            "metadata": {
                                "instanceType": "t3.micro",
                                "ami": "Amazon Linux 2",
                                "state": "running",
                                "preset": "web-server",
                                "publicIp": "Yes",
                                "monitoring": "Basic"
                            },
                            "style": {
                                "bgColor": "#E3F2FD",
                                "borderColor": "#1976D2",
                                "highlight": True
                            }
                        }
                    ]
                }
            ],
            "connections": [
                {
                    "id": "conn-1",
                    "source": "subnet-public-1",
                    "target": "igw",
                    "type": "reference",
                    "label": "routes via",
                    "style": {
                        "color": "#4CAF50"
                    }
                },
                {
                    "id": "conn-2",
                    "source": "rt-public",
                    "target": "igw",
                    "type": "reference",
                    "label": "0.0.0.0/0 →"
                },
                {
                    "id": "conn-3",
                    "source": "ec2-instance",
                    "target": "subnet-public-1",
                    "type": "hierarchy",
                    "label": "deployed in",
                    "style": {
                        "color": "#1976D2",
                        "width": 2
                    }
                },
                {
                    "id": "conn-4",
                    "source": "ec2-instance",
                    "target": "sg-app",
                    "type": "reference",
                    "label": "protected by",
                    "style": {
                        "color": "#AB47BC",
                        "dashed": True
                    }
                },
                {
                    "id": "conn-5",
                    "source": "ec2-instance",
                    "target": "iam-role",
                    "type": "reference",
                    "label": "uses role",
                    "style": {
                        "color": "#FFB300",
                        "dashed": True
                    }
                }
            ]
        }
