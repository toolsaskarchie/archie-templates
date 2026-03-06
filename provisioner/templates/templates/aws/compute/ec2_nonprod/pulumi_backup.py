"""
EC2 Non-Prod Template
Creates a single EC2 instance for development/testing with flexible VPC modes.

VPC Modes:
1. NEW VPC: Calls VPCSimpleNonprodTemplate + adds EC2 instance
2. EXISTING VPC: Uses existing VPC/subnet for EC2 instance

Validation: See VALIDATION.md for resource mapping and compliance.
"""
from typing import Any, Dict, Optional
import pulumi
import pulumi_aws as aws
from provisioner.templates.base import (
    InfrastructureTemplate,
    template_registry
)
from provisioner.utils.aws import get_standard_tags, ResourceNamer
from provisioner.utils.aws.cidr_utils import generate_random_vpc_cidr
import json
from provisioner.templates.templates.aws.compute.ec2_nonprod.config import EC2NonProdConfig
from provisioner.templates.templates.aws.networking.vpc_nonprod.pulumi import VPCSimpleNonprodTemplate
from provisioner.templates.atomic.aws.compute.ec2_atomic.pulumi import EC2AtomicTemplate
from provisioner.templates.atomic.aws.networking.security_group_atomic.pulumi import SecurityGroupAtomicTemplate
from provisioner.templates.atomic.aws.iam.iam_role_atomic.pulumi import IAMRoleAtomicTemplate
from provisioner.templates.atomic.aws.iam.iam_instance_profile_atomic.pulumi import IAMInstanceProfileAtomicTemplate
from provisioner.templates.shared.aws_schema import (
    get_project_env_schema, 
    get_vpc_selection_schema, 
    get_compute_selection_schema
)

@template_registry("aws-ec2-nonprod")
class EC2NonProdTemplate(InfrastructureTemplate):
    """
    EC2 Non-Production Instance
    Creates:
    - VPC with public/private subnets (if mode='new')
    - EC2 instance with optional key pair
    - Security groups for access control
    """
    def __init__(self, name: str = None, config: Dict[str, Any] = None, **kwargs):
        raw_config = config or kwargs or {}
        
        # Debug: Print what parameters we're receiving
        print(f"[EC2NonProd DEBUG] raw_config keys: {raw_config.keys()}")
        if 'parameters' in raw_config:
            print(f"[EC2NonProd DEBUG] parameters keys: {raw_config['parameters'].keys()}")
            if 'aws' in raw_config.get('parameters', {}):
                print(f"[EC2NonProd DEBUG] aws params: {raw_config['parameters']['aws'].keys()}")
        print(f"[EC2NonProd DEBUG] kwargs keys: {kwargs.keys()}")
        
        if name is None:
            name = raw_config.get('instanceName', 'ec2-nonprod')
        super().__init__(name, raw_config)
        self.cfg = EC2NonProdConfig(raw_config)
        # Layer 3 templates (called) - ALL resources use atomics
        self.vpc_template: Optional[VPCSimpleNonprodTemplate] = None
        self.ec2_instances: List[EC2AtomicTemplate] = []  # Support multiple instances
        self.security_group_atomic: Optional[SecurityGroupAtomicTemplate] = None
        self.iam_role_atomic: Optional[IAMRoleAtomicTemplate] = None
        self.instance_profile_atomic: Optional[IAMInstanceProfileAtomicTemplate] = None
    def create_infrastructure(self) -> Dict[str, Any]:
        # Strip description text from parameters if present
        vpc_mode = self.cfg.vpc_mode
        vpc_mode = vpc_mode.split('(')[0].strip() if isinstance(vpc_mode, str) and '(' in vpc_mode else vpc_mode
        
        # Initialize ResourceNamer
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
        
        instance_name = instance_name.split('(')[0].strip() if isinstance(instance_name, str) and '(' in instance_name else instance_name

        tags = namer.tags()
        
        # Resolve AMI dynamically based on OS selection
        ami_id = self.cfg.ami_id
        ami_id = ami_id.split('(')[0].strip() if isinstance(ami_id, str) and '(' in ami_id else ami_id
        ami_os = self.cfg.ami_os
        
        if ami_id.startswith('resolve-ssm:'):
            filters = []
            owners = []
            
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
            else:
                # Fallback to direct SSM if no filter defined
                print(f"[EC2] ⚠ No filter for OS '{ami_os}', using direct path.")
        # MODE 1: Call VPC template (Layer 3 calls Layer 3)
        base_security_groups = []
        if vpc_mode == 'new':
            print(f"[EC2] Calling VPC template for instance '{instance_name}'")
            
            # Use random VPC CIDR if configured
            vpc_cidr = self.cfg.vpc_cidr
            # Strip description text from vpc_cidr
            vpc_cidr = vpc_cidr.split('(')[0].strip() if isinstance(vpc_cidr, str) and '(' in vpc_cidr else vpc_cidr
            
            if self.cfg.use_random_vpc_cidr:
                vpc_cidr = generate_random_vpc_cidr()
            
            # Call VPC Template (Layer 3 template)
            # Note: Subnet CIDRs are auto-calculated from vpc_cidr in VPC template
            vpc_config = {
                "parameters": {
                    "aws": {
                        "project_name": self.cfg.project_name,
                        "cidr_block": vpc_cidr,
                        "environment": self.cfg.environment,
                        # VPC Configuration
                        "vpc_name": self.cfg.vpc_name,
                        "instance_tenancy": self.cfg.instance_tenancy,
                        "cidr_block": self.cfg.vpc_cidr,
                        
                        # DNS Configuration
                        "enable_dns_support": self.cfg.enable_dns_support,
                        "enable_dns_hostnames": self.cfg.enable_dns_hostnames,
                        
                        # Subnet Configuration
                        "public_subnet_1_cidr": self.cfg.public_subnet_1_cidr,
                        "public_subnet_2_cidr": self.cfg.public_subnet_2_cidr,
                        "private_subnet_1_cidr": self.cfg.private_subnet_1_cidr,
                        "private_subnet_2_cidr": self.cfg.private_subnet_2_cidr,
                        "az_1": self.cfg.az_1,
                        "az_2": self.cfg.az_2,
                        
                        # Connectivity & Security
                        "enable_nat_gateway": self.cfg.enable_nat_gateway,
                        "nat_gateway_count": self.cfg.nat_gateway_count,
                        "ssh_access_ip": self.cfg.ssh_access_ip,
                        "enable_ssm_endpoints": self.cfg.enable_ssm_endpoints,
                        "enable_s3_endpoint": self.cfg.enable_s3_endpoint,
                        "enable_dynamodb_endpoint": self.cfg.enable_dynamodb_endpoint,
                        "web_port": self.cfg.web_port,
                        "app_port": self.cfg.app_port,
                        "db_port": self.cfg.db_port,
                        
                        # Observability
                        "enable_flow_logs": self.cfg.enable_flow_logs,
                        "log_destination_type": self.cfg.log_destination_type,
                        "flow_log_retention": self.cfg.flow_log_retention
                    }
                }
            }

            
            # VPC template handles its own sub-resource naming using its own ResourceNamer
            self.vpc_template = VPCSimpleNonprodTemplate(
                name=f"{self.name}-vpc",
                config=vpc_config
            )
            self.vpc_template.create_infrastructure()
            vpc_outputs = self.vpc_template.get_outputs()
            
            vpc_id = vpc_outputs['vpc_id']
            # Use first public subnet for the EC2 instance
            subnet_id = vpc_outputs['public_subnet_ids'][0]
            
            # Use VPC security groups based on preset (VPC Foundation Pattern)
            preset = self.cfg.config_preset
            if preset in ['web-server', 'wordpress', 'nodejs']:
                # Web-based presets: Use app-sg for application + web-sg for HTTP/HTTPS
                if 'app_security_group_id' in vpc_outputs:
                    base_security_groups.append(vpc_outputs['app_security_group_id'])
                    print(f"[EC2] ✓ Using VPC's app security group for {preset}")
                if 'web_security_group_id' in vpc_outputs:
                    base_security_groups.append(vpc_outputs['web_security_group_id'])
                    print(f"[EC2] ✓ Using VPC's web security group for HTTP/HTTPS")
            elif preset in ['mysql', 'alb-backend']:
                # Backend/Database presets: Use app-sg 
                if 'app_security_group_id' in vpc_outputs:
                    base_security_groups.append(vpc_outputs['app_security_group_id'])
                    print(f"[EC2] ✓ Using VPC's app security group for {preset}")
            else:
                # Default preset: Use app-sg as general purpose
                if 'app_security_group_id' in vpc_outputs:
                    base_security_groups.append(vpc_outputs['app_security_group_id'])
                    print(f"[EC2] ✓ Using VPC's app security group (default)")
            
            # Always add access-sg for Remote Management (if configured)
            remote_ip = self.cfg.rdp_access_ip if ami_os == 'windows-2022' else self.cfg.ssh_access_ip
            
            if remote_ip and 'access_security_group_id' in vpc_outputs:
                access_sg_id = vpc_outputs['access_security_group_id']
                base_security_groups.append(access_sg_id)
                
                # Add rules to VPC's access-sg
                remote_port = 3389 if ami_os == 'windows-2022' else 22
                remote_proto = "RDP" if ami_os == 'windows-2022' else "SSH"
                
                print(f"[EC2] ✓ Adding {remote_proto} rules to VPC's access security group")
                
                # Handle single IP or list
                allowed_ips = [remote_ip] if isinstance(remote_ip, str) else remote_ip
                for idx, ip in enumerate(allowed_ips):
                    cidr_ip = ip if '/' in ip else f"{ip}/32"
                    aws.ec2.SecurityGroupRule(
                        f"{self.name}-{remote_proto.lower()}-rule-{idx}",
                        type="ingress",
                        security_group_id=access_sg_id,
                        protocol="tcp",
                        from_port=remote_port,
                        to_port=remote_port,
                        cidr_blocks=[cidr_ip],
                        description=f"{remote_proto} from {cidr_ip} for {instance_name}"
                    )
            
            print(f"[EC2] VPC template created with {len(base_security_groups)} security groups")
        
        # MODE 2: Use existing VPC
        else:
            vpc_id = self.cfg.vpc_id
            subnet_id = self.cfg.subnet_id
            print(f"[EC2] Using existing VPC and subnet")
            
            # For existing VPC mode: Create dedicated Access SG
            remote_ip = self.cfg.rdp_access_ip if ami_os == 'windows-2022' else self.cfg.ssh_access_ip
            remote_port = 3389 if ami_os == 'windows-2022' else 22
            remote_proto = "RDP" if ami_os == 'windows-2022' else "SSH"
            
            print(f"[EC2] ⚠ Creating dedicated {remote_proto} security group (existing VPC mode)")
            
            access_sg_ingress = []
            allowed_ips = [remote_ip] if isinstance(remote_ip, str) else remote_ip
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
                sg_config = {
                    "parameters": {
                        "aws": {
                            "security_group_name": access_sg_name,
                            "vpc_id": vpc_id,
                            "description": "SSH access security group",
                            "ingress": ssh_sg_ingress,
                            "egress": [{
                                "protocol": "-1",
                                "from_port": 0,
                                "to_port": 0,
                                "cidr_blocks": ["0.0.0.0/0"],
                                "description": "Allow all outbound"
                            }],
                            "project_name": self.cfg.project_name,
                            "environment": self.cfg.environment,
                            "region": self.cfg.region
                        }
                    }
                }
                
                self.security_group_atomic = SecurityGroupAtomicTemplate(
                    name=access_sg_name if 'access_sg_name' in locals() else f"{self.name}-access",
                    config=sg_config
                )
                self.security_group_atomic.create_infrastructure()
                sg_outputs = self.security_group_atomic.get_outputs()
                base_security_groups.append(sg_outputs['security_group_id'])
        
        # Collect all security group IDs: base VPC SGs + user-specified SGs
        security_group_ids = base_security_groups.copy()
        if self.cfg.security_group_ids:
            security_group_ids.extend(self.cfg.security_group_ids)
            print(f"[EC2] Added {len(self.cfg.security_group_ids)} additional security groups")
        
        # Create IAM Role and Instance Profile if SSM is enabled - use Atomics
        instance_profile_name = None
        if self.cfg.enable_ssm:
            print(f"[EC2] Creating IAM role via IAMRole Atomic")
            
            iam_role_name = namer.iam_role(service="ec2")
            
            # Create IAM Role using atomic
            iam_role_config = {
                "parameters": {
                    "aws": {
                        "role_name": iam_role_name,
                        "assume_role_policy": {
                            "Version": "2012-10-17",
                            "Statement": [{
                                "Effect": "Allow",
                                "Principal": {"Service": "ec2.amazonaws.com"},
                                "Action": "sts:AssumeRole"
                            }]
                        },
                        "managed_policy_arns": [
                            "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
                        ],
                        "inline_policies": {
                            "S3StaticAssetsRead": {
                                "Version": "2012-10-17",
                                "Statement": [
                                    {
                                        "Effect": "Allow",
                                        "Action": [
                                            "s3:GetObject"
                                        ],
                                        "Resource": [
                                            "arn:aws:s3:::archie-static-assets/*"
                                        ]
                                    }
                                ]
                            }
                        },
                        "project_name": self.cfg.project_name,
                        "environment": self.cfg.environment,
                        "region": self.cfg.region
                    }
                }
            }
            
            self.iam_role_atomic = IAMRoleAtomicTemplate(
                name=iam_role_name,
                config=iam_role_config
            )
            self.iam_role_atomic.create_infrastructure()
            role_outputs = self.iam_role_atomic.get_outputs()
            
            print(f"[EC2] Creating IAM instance profile via IAMInstanceProfile Atomic")
            
            profile_name = f"{iam_role_name}-profile"
            # Create Instance Profile using atomic
            instance_profile_config = {
                "parameters": {
                    "aws": {
                        "profile_name": profile_name,
                        "role_name": role_outputs['role_name'],
                        "project_name": self.cfg.project_name,
                        "environment": self.cfg.environment,
                        "region": self.cfg.region
                    }
                }
            }
            
            self.instance_profile_atomic = IAMInstanceProfileAtomicTemplate(
                name=profile_name,
                config=instance_profile_config
            )
            self.instance_profile_atomic.create_infrastructure()
            profile_outputs = self.instance_profile_atomic.get_outputs()
            
            instance_profile_name = profile_outputs['instance_profile_name']
        
        # Create EC2 instance using EC2 Atomic template (Layer 3)
        print(f"[EC2] Calling EC2 Atomic template for instance '{instance_name}'")

        # Log preset configuration
        if self.cfg.config_preset != 'custom':
            print(f"[EC2] Using preset configuration: {self.cfg.config_preset}")
            print(f"[EC2] Instance type: {self.cfg.instance_type}")
            print(f"[EC2] Open ports: {self.cfg.preset_ports}")
        
        # Build EC2 Atomic config
        ec2_atomic_config = {
            "parameters": {
                "aws": {
                    "instance_name": instance_name,
                    "ami_id": ami_id,
                    "instance_type": self.cfg.instance_type,
                    "subnet_id": subnet_id,
                    "security_group_ids": security_group_ids,
                    "iam_instance_profile": instance_profile_name,
                    "key_name": self.cfg.key_name,
                    "user_data": self.cfg.user_data,
                    "project_name": self.cfg.project_name,
                    "environment": self.cfg.environment,
                    "region": self.cfg.region
                }
            }
        }
        
        # Call EC2 Atomic template (Layer 3)
        self.ec2_atomic = EC2AtomicTemplate(
            name=instance_name,  # Use stable logical ID
            config=ec2_atomic_config
        )
        self.ec2_atomic.create_infrastructure()
        
        print(f"[EC2] Instance created successfully via EC2 Atomic template")
        
        # Get EC2 outputs from atomic template
        ec2_outputs = self.ec2_atomic.get_outputs()
        
        # Helper to serialize SG rules for readable outputs
        def serialize_sg_rules(rules):
            if not rules:
                return "[]"
            serialized = []
            for rule in rules:
                if isinstance(rule, dict):
                    # Filter out none values for cleaner JSON
                    clean_rule = {k: v for k, v in {
                        "protocol": rule.get("protocol", "-1"),
                        "from_port": rule.get("from_port"),
                        "to_port": rule.get("to_port"),
                        "cidr_blocks": rule.get("cidr_blocks", []),
                        "description": rule.get("description", "")
                    }.items() if v is not None}
                    serialized.append(clean_rule)
            return json.dumps(serialized, indent=2)

        # Export Pulumi outputs for user visibility
        pulumi.export("instance_id", ec2_outputs['instance_id'])
        
        # Dynamically generate display name via Output to include IP address
        # Use config preset if available, otherwise 'instance'
        preset_for_output = self.cfg.config_preset if self.cfg.config_preset != 'custom' else "instance"
        
        def generate_ip_name(ip):
             if not ip: return instance_name
             return namer.ec2_instance(preset=preset_for_output, ip_address=ip)

        # We prefer private IP for naming stability usually, but could be public if preferred. 
        # User example was "235.4.45" which looks like private IP segment.
        display_name = ec2_outputs['private_ip'].apply(generate_ip_name)
        
        pulumi.export("instance_name", display_name)
        pulumi.export("private_ip", ec2_outputs['private_ip'])
        pulumi.export("public_ip", ec2_outputs.get('public_ip'))
        
        # Export website URL for web-server preset
        if self.cfg.config_preset == 'web-server' and ec2_outputs.get('public_ip'):
            website_url = pulumi.Output.concat("http://", ec2_outputs['public_ip'])
            pulumi.export("website_url", website_url)
            pulumi.export("congratulations", 
                pulumi.Output.concat(
                    "🎉 Your Archie Static Website is live at: http://",
                    ec2_outputs['public_ip']
                ))
        
        # Export SSM connection command if SSM is enabled
        if self.cfg.enable_ssm:
            ssm_command = pulumi.Output.concat(
                "aws ssm start-session --target ", 
                ec2_outputs['instance_id'],
                " --region ",
                self.cfg.region
            )
            pulumi.export("ssm_connect", ssm_command)
        
        # Export SSH command if key pair is provided
        if self.cfg.key_name and ec2_outputs.get('public_ip'):
            ssh_command = pulumi.Output.concat(
                "ssh -i ~/.ssh/",
                self.cfg.key_name,
                ".pem ec2-user@",
                ec2_outputs['public_ip']
            )
            pulumi.export("ssh_connect", ssh_command)
            
        # Export SSH Security Group Rules if created (Existing VPC Mode)
        if 'ssh_sg_ingress' in locals():
             pulumi.export("ssh_security_group_ingress", serialize_sg_rules(ssh_sg_ingress))
        
        # Export VPC info if created
        if self.vpc_template:
            pulumi.export("vpc_id", vpc_id)
            pulumi.export("vpc_cidr", vpc_cidr)
        
        return {
            "instance_id": ec2_outputs['instance_id'],
            "vpc_id": vpc_id,
            "subnet_id": subnet_id
        }
    
    def get_outputs(self) -> Dict[str, Any]:
        """Get template outputs"""
        if not self.ec2_atomic:
            return {
                "instance_name": self.cfg.instance_name,
                "instance_type": self.cfg.instance_type,
                "status": "not_created"
            }
        
        # Get outputs from EC2 Atomic template
        ec2_outputs = self.ec2_atomic.get_outputs()
        
        outputs = {
            "instance_id": ec2_outputs.get('instance_id'),
            "instance_name": self.cfg.instance_name,
            "instance_type": self.cfg.instance_type,
            "private_ip": ec2_outputs.get('private_ip'),
        }
        
        # Add public IP if instance has one
        if ec2_outputs.get('public_ip'):
            outputs["public_ip"] = ec2_outputs['public_ip']
        
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
            outputs["public_subnet_ids"] = vpc_outputs.get("public_subnet_ids")
            outputs["private_subnet_ids"] = vpc_outputs.get("private_subnet_ids")
        
        # Add IAM role info if we created it
        if self.iam_role_atomic:
            role_outputs = self.iam_role_atomic.get_outputs()
            outputs["iam_role_arn"] = role_outputs.get("role_arn")
            outputs["iam_role_name"] = role_outputs.get("role_name")
        
        # Add IAM instance profile info if we created it
        if self.instance_profile_atomic:
            profile_outputs = self.instance_profile_atomic.get_outputs()
            outputs["iam_instance_profile_arn"] = profile_outputs.get("instance_profile_arn")
            outputs["iam_instance_profile_name"] = profile_outputs.get("instance_profile_name")
        
        # Add SSH security group info (if created)
        if self.security_group_atomic:
            sg_outputs = self.security_group_atomic.get_outputs()
            outputs["ssh_security_group_id"] = sg_outputs.get("security_group_id")
        
        return outputs
    
    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        """Get configuration schema for the UI"""
        return EC2NonProdConfig.get_config_schema()

    @classmethod
    def get_metadata(cls):
        """Get template metadata"""
        from provisioner.templates.base.template import TemplateMetadata, TemplateCategory
        return TemplateMetadata(
            name="aws-ec2-nonprod",
            title="Simple EC2 (Non-Prod)",
            description="Complete cost-optimized EC2 infrastructure for development, staging, and testing environments. Choose between creating a new VPC with full networking setup (subnets, internet gateway, NAT gateway, route tables, security groups) or deploying into an existing VPC. Includes EC2 instance with IAM role/profile, multiple application presets (Web Server, WordPress, MySQL, Node.js, ALB Backend, Custom), pre-configured security groups for SSH access, application traffic, database connections, and web services. Features VPC endpoints for S3 and DynamoDB, VPC Flow Logs for monitoring, and AWS Systems Manager (SSM) integration for secure instance management without SSH keys. Supports both public and private subnet deployments with optional NAT gateway for private subnet internet access. Automatically assigns appropriate security groups based on application preset (web presets get HTTP/HTTPS access, database presets get app security groups). Creates IAM roles with SSM managed policies and S3 read access for static assets. Exports instance details, IP addresses, VPC information, and connection commands for SSH and SSM access.",
            category=TemplateCategory.Kubernetes,
            version="1.1.0",
            author="Archielabs",
            tags=["ec2", "compute", "development", "nonprod", "cost-optimized"],
            features=[
                "Flexible VPC Integration (New/Existing VPC)",
                "Application/Stack Presets (Web, Node.js, DB)",
                "Cost-Effective t3-Family Instance Support",
                "Integrated Security Group presets for Common Ports",
                "Secure Access via SSH or AWS Systems Manager (SSM)",
                "S3 Integration for Static Assets & Deployment"
            ],
            estimated_cost="$10-35/month (Burstable performance)",
            complexity="medium",
            deployment_time="5-8 minutes"
        )
    
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
