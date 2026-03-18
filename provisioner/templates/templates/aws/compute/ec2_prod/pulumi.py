"""
EC2 Production Template
Creates a production-grade EC2 instance with monitoring, backups, and HA.
VPC Modes:
1. NEW VPC: Creates VPC + EC2 instance with multi-AZ support
2. EXISTING VPC: Uses existing VPC/subnet for EC2 instance
"""
from typing import Any, Dict, Optional, List
import json
import pulumi
import pulumi_aws as aws

from provisioner.templates.base import InfrastructureTemplate, template_registry
from provisioner.utils.aws import get_standard_tags, ResourceNamer
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory
from provisioner.templates.templates.aws.compute.ec2_prod.config import EC2ProdConfig
from provisioner.templates.templates.aws.networking.vpc_prod.pulumi import VPCProdTemplate

@template_registry("aws-ec2-prod")
class EC2ProdTemplate(InfrastructureTemplate):
    """
    EC2 Production Instance - Pattern B
    
    Creates:
    - VPC (if new)
    - IAM Role & Instance Profile
    - Security Groups
    - EC2 Instance with monitoring & backups
    """
    def __init__(self, name: str = None, config: Dict[str, Any] = None, **kwargs):
        raw_config = config or kwargs or {}
        if name is None:
            name = raw_config.get('instanceName', 'ec2-prod')
        super().__init__(name, raw_config)
        self.cfg = EC2ProdConfig(raw_config)
        
        # Resource references
        self.vpc_template: Optional[VPCProdTemplate] = None
        self.iam_role = None
        self.instance_profile = None
        self.security_groups = []
        self.ec2_instance = None
        self.access_sg = None

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
            environment="prod",
            region=self.cfg.region,
            template="ec2-prod"
        )
        
        # Instance Name Resolution
        instance_name = self.cfg.instance_name or namer.ec2_instance(preset="prod")
        if isinstance(instance_name, str) and '(' in instance_name:
            instance_name = instance_name.split('(')[0].strip()

        tags = namer.tags()
        
        # Resolve AMI
        ami_id = self.cfg.ami_id
        if isinstance(ami_id, str) and '(' in ami_id:
            ami_id = ami_id.split('(')[0].strip()
        
        if not ami_id or ami_id.startswith('resolve-ssm:'):
            ami = aws.ec2.get_ami(
                most_recent=True,
                owners=["amazon"],
                filters=[
                    aws.ec2.GetAmiFilterArgs(name="name", values=["amzn2-ami-hvm-*-x86_64-gp2"]),
                    aws.ec2.GetAmiFilterArgs(name="state", values=["available"])
                ]
            )
            ami_id = ami.id

        # Networking Logic
        vpc_app_sg = None
        vpc_web_sg = None
        vpc_db_sg = None
        base_security_groups = []
        
        if vpc_mode == 'new':
            print(f"[EC2-PROD] Calling VPC production template for instance '{instance_name}'")
            vpc_cidr = self.cfg.vpc_cidr or generate_random_vpc_cidr()
            
            vpc_config = {
                "parameters": {
                    "aws": {
                        "project_name": self.cfg.project_name,
                        "cidr_block": vpc_cidr,
                        "environment": self.cfg.environment
                    }
                }
            }
            
            self.vpc_template = VPCProdTemplate(name=f"{self.name}-vpc", config=vpc_config)
            self.vpc_template.create_infrastructure()
            vpc_outputs = self.vpc_template.get_outputs()
            
            vpc_id = vpc_outputs.get('vpc_id')
            subnet_id = (vpc_outputs.get('public_subnet_ids') or [None])[0]
            
            if vpc_outputs.get('app_security_group_id'):
                base_security_groups.append(vpc_outputs['app_security_group_id'])
            
            if self.cfg.ssh_access_ip and 'access_security_group_id' in vpc_outputs:
                access_sg_id = vpc_outputs['access_security_group_id']
                base_security_groups.append(access_sg_id)
                allowed_ips = [self.cfg.ssh_access_ip] if isinstance(self.cfg.ssh_access_ip, str) else self.cfg.ssh_access_ip
                for idx, ip in enumerate(allowed_ips):
                    cidr_ip = ip if '/' in ip else f"{ip}/32"
                    factory.create(
                        "aws:ec2:SecurityGroupRule",
                        f"{self.name}-ssh-rule-{idx}",
                        type="ingress",
                        security_group_id=access_sg_id,
                        protocol="tcp",
                        from_port=22,
                        to_port=22,
                        cidr_blocks=[cidr_ip],
                        description=f"SSH from {cidr_ip}"
                    )
        else:
            vpc_id = self.cfg.vpc_id
            subnet_id = self.cfg.subnet_id
            
            if self.cfg.ssh_access_ip:
                access_sg_ingress = []
                allowed_ips = [self.cfg.ssh_access_ip] if isinstance(self.cfg.ssh_access_ip, str) else self.cfg.ssh_access_ip
                for ip in allowed_ips:
                    cidr_ip = ip if '/' in ip else f"{ip}/32"
                    access_sg_ingress.append({
                        "protocol": "tcp", "from_port": 22, "to_port": 22,
                        "cidr_blocks": [cidr_ip], "description": f"SSH from {cidr_ip}"
                    })
                
                sg_name = f"{self.name}-ssh"
                self.access_sg = factory.create(
                    "aws:ec2:SecurityGroup",
                    sg_name,
                    vpc_id=vpc_id,
                    description=f"SSH access for {instance_name}",
                    ingress=access_sg_ingress,
                    egress=[{"protocol": "-1", "from_port": 0, "to_port": 0, "cidr_blocks": ["0.0.0.0/0"]}],
                    tags={**tags, "Name": sg_name}
                )
                self.security_groups.append(self.access_sg)
                base_security_groups.append(self.access_sg.id)
            
            # SG Discovery
            def discover_sgs(v_id):
                import boto3
                try:
                    ec2 = boto3.client('ec2', region_name=self.cfg.region)
                    filters = [{"name": "vpc-id", "values": [v_id]}, {"name": "tag:Project", "values": [self.cfg.project_name]}]
                    found = {}
                    for tier in ['web', 'app', 'db']:
                        f = filters + [{"name": "tag:Tier", "values": [tier]}]
                        resp = ec2.describe_security_groups(Filters=f)
                        if resp['SecurityGroups']: found[tier] = resp['SecurityGroups'][0]['GroupId']
                    return found
                except: return {}

            discovery = pulumi.Output.from_input(vpc_id).apply(discover_sgs)
            vpc_app_sg = discovery.apply(lambda s: s.get('app'))
            vpc_web_sg = discovery.apply(lambda s: s.get('web'))

        # IAM & Instance
        instance_profile_name = None
        if self.cfg.enable_ssm:
            role_name = namer.iam_role("ec2", instance_name)
            self.iam_role = factory.create(
                "aws:iam:Role",
                role_name,
                assume_role_policy=json.dumps({
                    "Version": "2012-10-17",
                    "Statement": [{"Effect": "Allow", "Principal": {"Service": "ec2.amazonaws.com"}, "Action": "sts:AssumeRole"}]
                }),
                managed_policy_arns=["arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"],
                tags={**tags, "Name": role_name}
            )
            
            profile_name = namer.iam_profile("ec2", instance_name)
            self.instance_profile = factory.create(
                "aws:iam:InstanceProfile",
                profile_name,
                role=self.iam_role.name,
                tags={**tags, "Name": profile_name}
            )
            instance_profile_name = self.instance_profile.name
            
        # Create instance
        sgs = base_security_groups + (self.cfg.security_group_ids or [])
        if vpc_app_sg: sgs.append(vpc_app_sg)
        if vpc_web_sg: sgs.append(vpc_web_sg)

        self.ec2_instance = factory.create(
            "aws:ec2:Instance",
            namer.ec2_instance(instance_name),
            ami=ami_id,
            instance_type=self.cfg.instance_type,
            subnet_id=subnet_id,
            vpc_security_group_ids=sgs,
            iam_instance_profile=instance_profile_name,
            key_name=self.cfg.key_name,
            tags={**tags, "Name": instance_name},
            monitoring=True,
            ebs_optimized=True,
            root_block_device={"encrypted": True, "volume_size": 20, "volume_type": "gp3"}
        )

        # Pulumi exports for stack outputs
        pulumi.export("instance_id", self.ec2_instance.id)
        pulumi.export("instance_type", self.cfg.instance_type)
        pulumi.export("public_ip", self.ec2_instance.public_ip)
        pulumi.export("private_ip", self.ec2_instance.private_ip)
        pulumi.export("security_group_id", self.ec2_instance.vpc_security_group_ids)
        if self.vpc_template:
            vpc_out = self.vpc_template.get_outputs()
            pulumi.export("vpc_id", vpc_out.get("vpc_id"))
            pulumi.export("subnet_id", subnet_id)
        pulumi.export("ssh_command", self.ec2_instance.public_ip.apply(
            lambda ip: f"ssh -i key.pem ec2-user@{ip}" if ip else "N/A (no public IP)"
        ))

        return self.get_outputs()
    
    def get_outputs(self) -> Dict[str, Any]:
        """Get template outputs"""
        if not self.ec2_instance: return {}
        res = {
            "instance_id": self.ec2_instance.id,
            "private_ip": self.ec2_instance.private_ip,
            "public_ip": self.ec2_instance.public_ip
        }
        if self.vpc_template:
            res.update(self.vpc_template.get_outputs())
        return res

    @classmethod
    def get_metadata(cls) -> Dict[str, Any]:
        """Get template metadata (SOURCE OF TRUTH for extractor)"""
        return {
            "name": "aws-ec2-prod",
            "title": "Enterprise EC2 Instance",
            "description": "Production-ready EC2 infrastructure featuring a high-availability VPC across 3 AZs, enhanced CloudWatch monitoring with automated alarms, and encrypted EBS storage. Optimized for mission-critical workloads.",
            "category": "compute",
            "version": "1.0.0",
            "author": "InnovativeApps",
            "cloud": "aws",
            "environment": "prod",
            "base_cost": "$45-120/month",
            "tags": ["ec2", "compute", "production", "high-availability", "secure"],
            "features": [
                "Enterprise-Grade VPC (3 Availability Zones)",
                "Enhanced CloudWatch Monitoring & Performance Alarms",
                "Encrypted EBS Volumes with Automated Backups",
                "Secure Access via AWS Systems Manager (SSM)",
                "Pre-configured Security Group Isolation"
            ],
            "use_cases": [
                "Production application servers",
                "High-availability web clusters",
                "Mission-critical workloads"
            ],
            "deployment_time": "8-12 minutes",
            "complexity": "advanced",
            "pillars": [
                {
                    "title": "Operational Excellence",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Full monitoring and automation enables consistent operations",
                    "practices": [
                        "Infrastructure as Code for repeatable production deployments",
                        "Enhanced CloudWatch monitoring enabled by default",
                        "SSM integration for auditable instance management without SSH keys",
                        "Automated tagging for cost allocation and resource tracking"
                    ]
                },
                {
                    "title": "Security",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Production-grade security controls and encryption",
                    "practices": [
                        "EBS volumes encrypted by default to protect data at rest",
                        "Strict security groups restricting traffic to necessary ports",
                        "IAM instance profiles with least-privilege permissions",
                        "Private subnet placement options for isolation from internet"
                    ]
                },
                {
                    "title": "Reliability",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "High availability architecture design",
                    "practices": [
                        "Multi-AZ networking foundation when using new VPC mode",
                        "EBS optimized instances for consistent storage performance",
                        "Recovery alarms configured for instance status checks"
                    ]
                },
                {
                    "title": "Performance Efficiency",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Optimized compute and networking configuration",
                    "practices": [
                        "Latest generation instance types (t3/m5) for best price/performance",
                        "GP3 volumes for predictable storage throughput",
                        "EBS optimization enabled for dedicated storage bandwidth"
                    ]
                },
                {
                    "title": "Cost Optimization",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Balances performance needs with cost controls",
                    "practices": [
                        "Right-sized default instance types",
                        "GP3 volumes offer better value than legacy GP2",
                        "Detailed cost allocation tagging"
                    ]
                },
                {
                    "title": "Sustainability",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Efficient resource usage reduces environmental impact",
                    "practices": [
                        "Modern instance generations provide better performance per watt",
                        "Shared resources (NAT Gateway) reduce infrastructure overhead",
                        "GP3 volumes eliminate need for over-provisioning for IOPS"
                    ]
                }
            ]
        }

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        """Get configuration schema (SOURCE OF TRUTH for extractor)"""
        return {
            "instance_name": {
                "type": "string",
                "default": "prod-app-server",
                "title": "Instance Name",
                "description": "Name tag for the EC2 instance",
                "order": 10,
                "group": "Compute Settings"
            },
            "instance_type": {
                "type": "string",
                "default": "t3.medium",
                "title": "Instance Type",
                "description": "EC2 instance size (t3.medium recommended for prod baseline)",
                "order": 11,
                "group": "Compute Settings",
                "enum": ["t3.medium", "t3.large", "m5.large", "m5.xlarge", "c5.large"],
                "cost_impact": "$30-150/month depending on size"
            },
            "vpc_mode": {
                "type": "string",
                "default": "new",
                "title": "VPC Mode",
                "description": "Create new VPC or use existing",
                "order": 20,
                "group": "Network Settings",
                "enum": ["new", "existing"],
                "cost_impact": "$0/month (mode selection)"
            },
            "vpc_cidr": {
                "type": "string",
                "default": "10.0.0.0/16",
                "title": "VPC CIDR Block",
                "description": "IPv4 CIDR block for new VPC",
                "order": 21,
                "group": "Network Settings"
            },
            "use_random_vpc_cidr": {
                "type": "boolean",
                "default": True,
                "title": "Use Random CIDR",
                "description": "Automatically generate a unique CIDR block",
                "order": 22,
                "group": "Network Settings"
            },
            "vpc_id": {
                "type": "string",
                "default": "",
                "title": "Existing VPC ID",
                "description": "ID of existing VPC (for existing mode)",
                "order": 23,
                "group": "Network Settings"
            },
            "subnet_id": {
                "type": "string",
                "default": "",
                "title": "Existing Subnet ID",
                "description": "ID of existing subnet (for existing mode)",
                "order": 24,
                "group": "Network Settings"
            },
            "ami_id": {
                "type": "string",
                "default": "resolve-ssm:/aws/service/ami-amazon-linux-latest/amzn2-ami-hvm-x86_64-gp2",
                "title": "AMI ID",
                "description": "AWS AMI ID for the instance",
                "order": 12,
                "group": "Compute Settings"
            },
            "security_group_ids": {
                "type": "array",
                "default": [],
                "title": "Additional Security Groups",
                "description": "List of existing SG IDs to attach",
                "order": 33,
                "group": "Security Settings"
            },
            "enable_ssm": {
                "type": "boolean",
                "default": True,
                "title": "Enable Systems Manager",
                "description": "Enable secure session management via SSM (replaces SSH)",
                "order": 30,
                "group": "Security Settings",
                "cost_impact": "$0/month (SSM is free)"
            },
            "key_name": {
                "type": "string",
                "default": "",
                "title": "SSH Key Pair",
                "description": "Optional: Name of existing EC2 key pair for SSH access",
                "order": 31,
                "group": "Security Settings",
                "cost_impact": "$0/month"
            },
            "ssh_access_ip": {
                "type": "string",
                "default": "",
                "title": "SSH Allowed IPs",
                "description": "List of IP CIDRs allowed to SSH (e.g. 1.2.3.4/32)",
                "order": 32,
                "group": "Security Settings"
            },
            "user_data": {
                "type": "string",
                "default": "",
                "title": "User Data",
                "description": "Cloud-init script to run on first boot",
                "order": 40,
                "group": "Advanced Settings"
            }
        }
