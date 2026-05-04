"""
Configuration parser for ALB Non-Prod Template
"""
from typing import Dict, Any, Optional, List

class ALBNonProdConfig:
    """Parsed and validated configuration for ALB Non-Prod Template"""

    def __init__(self, template_or_config: Any):
        """Parse configuration from user input or template instance"""
        if hasattr(template_or_config, 'get_parameter'):
            self.template = template_or_config
            self.raw_config = self.template.config
        else:
            self.template = None
            self.raw_config = template_or_config

        self.parameters = self.raw_config.get('parameters', {}).get('aws', {}) or self.raw_config.get('parameters', {})
        
        # Core attributes
        self.environment = self.raw_config.get('environment', 'nonprod')
        self.region = self.raw_config.get('region', 'us-east-1')
        self.tags = self.raw_config.get('tags', {})

        # Load Balancer Settings
        self.alb_name = self.get_parameter('alb_name', self.get_parameter('albName', 'alb-nonprod'))
        self.internal = self.get_parameter('internal', False)
        self.enable_https = self.get_parameter('enable_https', self.get_parameter('enableHttps', False))
        self.certificate_arn = self.get_parameter('certificate_arn', self.get_parameter('certificateArn'))
        
        # Target Settings
        self.target_port = int(self.get_parameter('target_port', self.get_parameter('targetPort', 80)))
        self.target_protocol = self.get_parameter('target_protocol', self.get_parameter('targetProtocol', 'HTTP'))
        self.ec2_instance_count = int(self.get_parameter('ec2_instance_count', self.get_parameter('ec2InstanceCount', 2)))
        self.ec2_instance_type = self.get_parameter('ec2_instance_type', self.get_parameter('ec2InstanceType', 't3.micro'))
        
        # Networking & Connectivity
        self.vpc_mode = self.get_parameter('vpc_mode', self.get_parameter('vpcMode', 'new'))
        self.vpc_id = self.get_parameter('vpc_id', self.get_parameter('vpcId'))
        self.vpc_cidr = self.get_parameter('vpc_cidr', self.get_parameter('vpcCidr', '10.0.0.0/16'))
        self.use_random_vpc_cidr = self.get_parameter('use_random_vpc_cidr', self.get_parameter('useRandomVpcCidr', True))
        
        self.ssh_access_ip = self.get_parameter('ssh_access_ip', self.get_parameter('sshAccessIp'))
        if self.ssh_access_ip and '/' not in self.ssh_access_ip:
            self.ssh_access_ip = f"{self.ssh_access_ip}/32"

        self.allowed_ips = self.get_parameter('allowed_ips', self.get_parameter('allowedIps'))
        if not self.allowed_ips:
            # For non-prod ALB, restricted to SSH access IP by default if provided, else open
            self.allowed_ips = [self.ssh_access_ip] if self.ssh_access_ip else ['0.0.0.0/0']
        elif isinstance(self.allowed_ips, str):
            self.allowed_ips = [self.allowed_ips]

    def get_parameter(self, key: str, default: Any = None) -> Any:
        """Get a parameter from the configuration."""
        if self.template:
            return self.template.get_parameter(key, default)
        return self.parameters.get(key, default)

    @property
    def project_name(self) -> str:
        """Get project name from config."""
        return (
            self.get_parameter('projectName') or
            self.get_parameter('project_name') or
            self.raw_config.get('projectName') or
            self.raw_config.get('project_name') or
            'archie-alb-nonprod'
        )

    @staticmethod
    def get_config_schema() -> Dict[str, Any]:
        """Get JSON schema for UI configuration."""
        return {
            "type": "object",
            "properties": {
                # --- Essentials ---
                "project_name": {
                    "type": "string",
                    "title": "Project Name",
                    "description": "Unique name for this project (used in resource naming)",
                    "group": "Essentials",
                    "isEssential": True,
                    "order": 1
                },
                "region": {
                    "type": "string",
                    "title": "AWS Region",
                    "description": "AWS region to deploy into",
                    "default": "us-east-1",
                    "enum": ["us-east-1", "us-east-2", "us-west-1", "us-west-2", "eu-west-1", "eu-central-1", "ap-southeast-1"],
                    "group": "Essentials",
                    "isEssential": True,
                    "order": 2
                },
                # --- Load Balancer ---
                "alb_name": {
                    "type": "string",
                    "title": "ALB Name",
                    "description": "Unique name for the load balancer",
                    "placeholder": "Auto-generated",
                    "group": "Load Balancer",
                    "isEssential": True,
                    "order": 10
                },
                "internal": {
                    "type": "boolean",
                    "title": "Internal Load Balancer",
                    "description": "Whether the load balancer is internal-only (not internet-facing)",
                    "default": False,
                    "group": "Load Balancer",
                    "order": 11
                },
                "enable_https": {
                    "type": "boolean",
                    "title": "Enable HTTPS (SSL)",
                    "description": "Enable secure listener on port 443",
                    "default": False,
                    "group": "Load Balancer",
                    "isEssential": True,
                    "order": 12
                },
                "certificate_arn": {
                    "type": "string",
                    "title": "ACM Certificate ARN",
                    "description": "ARN of existing ACM certificate for HTTPS",
                    "placeholder": "arn:aws:acm:...",
                    "visibleIf": {"enable_https": True},
                    "group": "Load Balancer",
                    "order": 13
                },
                "target_port": {
                    "type": "number",
                    "title": "Backend Port",
                    "description": "Port on the EC2 instances to route traffic to",
                    "default": 80,
                    "group": "Load Balancer",
                    "order": 14
                },
                # --- Compute ---
                "ec2_instance_count": {
                    "type": "number",
                    "title": "Instance Count",
                    "description": "Number of backend EC2 instances",
                    "default": 2,
                    "minimum": 1,
                    "maximum": 10,
                    "group": "Compute",
                    "isEssential": True,
                    "order": 20
                },
                "ec2_instance_type": {
                    "type": "string",
                    "title": "Instance Type",
                    "description": "EC2 instance size for backend targets",
                    "default": "t3.micro",
                    "enum": ["t3.micro", "t3.small", "t3.medium", "t3.large", "t3.xlarge"],
                    "group": "Compute",
                    "order": 21
                },
                # --- Networking ---
                "vpc_mode": {
                    "type": "string",
                    "title": "VPC Mode",
                    "description": "Create a new VPC or use an existing one",
                    "default": "new",
                    "enum": ["new", "existing"],
                    "group": "Networking",
                    "isEssential": True,
                    "order": 30
                },
                "vpc_id": {
                    "type": "string",
                    "title": "Existing VPC ID",
                    "description": "ID of an existing VPC to deploy into",
                    "placeholder": "vpc-0abc123def456",
                    "visibleIf": {"vpc_mode": "existing"},
                    "group": "Networking",
                    "order": 31
                },
                "vpc_cidr": {
                    "type": "string",
                    "title": "VPC CIDR Block",
                    "description": "CIDR block for the new VPC (leave empty for auto-generated)",
                    "placeholder": "10.0.0.0/16",
                    "visibleIf": {"vpc_mode": "new"},
                    "group": "Networking",
                    "order": 32
                },
                # --- Security ---
                "ssh_access_ip": {
                    "type": "string",
                    "title": "SSH Access IP",
                    "description": "IP address allowed for SSH to backend instances",
                    "placeholder": "203.0.113.0/32",
                    "group": "Security",
                    "order": 40
                },
                "allowed_ips": {
                    "type": "string",
                    "title": "Allowed IPs",
                    "description": "Comma-separated IPs allowed to reach the ALB (default: 0.0.0.0/0)",
                    "placeholder": "0.0.0.0/0",
                    "group": "Security",
                    "order": 41
                },
                # --- VPC Configuration (when vpc_mode=new) ---
                "use_custom_cidr": {
                    "type": "boolean",
                    "title": "Use Custom CIDR",
                    "description": "Specify a custom CIDR block instead of auto-generated",
                    "default": False,
                    "visibleIf": {"vpc_mode": "new"},
                    "group": "VPC Configuration",
                    "order": 50
                },
                "custom_cidr_block": {
                    "type": "string",
                    "title": "Custom CIDR Block",
                    "description": "Custom VPC CIDR block (e.g. 10.0.0.0/16)",
                    "placeholder": "10.0.0.0/16",
                    "visibleIf": {"use_custom_cidr": True, "vpc_mode": "new"},
                    "group": "VPC Configuration",
                    "order": 51
                },
                "enable_dns_support": {
                    "type": "boolean",
                    "title": "Enable DNS Support",
                    "description": "Enable DNS resolution within the VPC",
                    "default": True,
                    "visibleIf": {"vpc_mode": "new"},
                    "group": "VPC Configuration",
                    "order": 52
                },
                "enable_dns_hostnames": {
                    "type": "boolean",
                    "title": "Enable DNS Hostnames",
                    "description": "Enable DNS hostnames for instances in the VPC",
                    "default": True,
                    "visibleIf": {"vpc_mode": "new"},
                    "group": "VPC Configuration",
                    "order": 53
                },
                "ssh_access_ip_vpc": {
                    "type": "string",
                    "title": "SSH Access IP/CIDR",
                    "description": "IP address or CIDR block allowed for SSH access",
                    "placeholder": "203.0.113.0/32",
                    "visibleIf": {"vpc_mode": "new"},
                    "group": "VPC Configuration",
                    "order": 54
                },
                "enable_nat_gateway": {
                    "type": "boolean",
                    "title": "Enable NAT Gateway",
                    "description": "Enable NAT gateway for private subnet internet access",
                    "default": True,
                    "cost_impact": "$32/mo per gateway",
                    "visibleIf": {"vpc_mode": "new"},
                    "group": "VPC Configuration",
                    "order": 55
                },
                "enable_ssh_access": {
                    "type": "boolean",
                    "title": "Enable SSH Security Group",
                    "description": "Create a security group allowing SSH access",
                    "default": False,
                    "visibleIf": {"vpc_mode": "new"},
                    "group": "VPC Configuration",
                    "order": 56
                },
                "enable_flow_logs": {
                    "type": "boolean",
                    "title": "Enable VPC Flow Logs",
                    "description": "Enable VPC flow logs for network monitoring",
                    "default": True,
                    "visibleIf": {"vpc_mode": "new"},
                    "group": "VPC Configuration",
                    "order": 57
                },
                "flow_log_retention": {
                    "type": "number",
                    "title": "Flow Logs Retention (days)",
                    "description": "Number of days to retain VPC flow logs",
                    "default": 7,
                    "visibleIf": {"vpc_mode": "new"},
                    "group": "VPC Configuration",
                    "order": 58
                },
                "enable_rds_endpoint": {
                    "type": "boolean",
                    "title": "Enable RDS VPC Endpoint",
                    "description": "Create a VPC endpoint for RDS access",
                    "default": False,
                    "visibleIf": {"vpc_mode": "new"},
                    "group": "VPC Configuration",
                    "order": 59
                },
                "enable_ssm_endpoints": {
                    "type": "boolean",
                    "title": "Enable SSM VPC Endpoints",
                    "description": "Create VPC endpoints for AWS Systems Manager",
                    "default": True,
                    "cost_impact": "$22/mo",
                    "visibleIf": {"vpc_mode": "new"},
                    "group": "VPC Configuration",
                    "order": 60
                },
                "team_name": {
                    "type": "string",
                    "default": "",
                    "title": "Team Name",
                    "description": "Team that owns this resource",
                    "order": 70,
                    "group": "Tags",
                },
            },
            "required": ["project_name"]
        }
