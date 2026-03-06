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
        from provisioner.templates.templates.aws.networking.vpc_nonprod.pulumi import VPCSimpleNonprodTemplate
        from provisioner.templates.templates.aws.compute.ec2_nonprod.config import EC2NonProdConfig
        
        # Pull base schemas
        vpc_schema = VPCSimpleNonprodTemplate.get_config_schema()
        ec2_schema = EC2NonProdConfig.get_config_schema()
        
        # Merge logic: ALB specific fields + VPC base + EC2 base
        # We use order_offset to handle prioritization if needed, but here we just merge properties
        properties = {
            # Shared essentials (handled by both, so any is fine)
            **vpc_schema.get("properties", {}),
            # Merge EC2 compute/security fields
            **ec2_schema.get("properties", {}),
        }
        
        # ALB Specific overrides/additions
        properties.update({
            "alb_header": {
                "type": "separator",
                "title": "Load Balancer Settings",
                "group": "Load Balancer",
                "isEssential": True,
                "order": 140
            },
            "alb_name": {
                "type": "string",
                "title": "ALB Name",
                "description": "Unique name for the load balancer",
                "placeholder": "Auto-generated",
                "group": "Load Balancer",
                "isEssential": True,
                "order": 141
            },
            "internal": {
                "type": "boolean",
                "title": "Internal Load Balancer",
                "description": "Whether the load balancer is internal-only",
                "default": False,
                "group": "Load Balancer",
                "order": 142
            },
            "enable_https": {
                "type": "boolean",
                "title": "Enable HTTPS (SSL)",
                "description": "Enable secure listener on port 443",
                "default": False,
                "group": "Load Balancer",
                "isEssential": True,
                "order": 143
            },
            "certificate_arn": {
                "type": "string",
                "title": "ACM Certificate ARN",
                "description": "ARN of existing ACM certificate",
                "placeholder": "arn:aws:acm:...",
                "visibleIf": {"enable_https": True},
                "group": "Load Balancer",
                "order": 144
            },
            "target_port": {
                "type": "number",
                "title": "Backend Port",
                "description": "Port on the EC2 instances to route traffic to",
                "default": 80,
                "group": "Load Balancer",
                "order": 145
            }
        })
        
        return {
            "type": "object",
            "properties": properties,
            "required": list(set(vpc_schema.get("required", []) + ec2_schema.get("required", []) + ["alb_name"]))
        }
