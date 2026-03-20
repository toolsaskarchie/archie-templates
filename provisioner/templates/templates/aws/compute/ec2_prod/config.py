"""
Configuration parser for EC2 Production Template
"""
from typing import Dict, Any, Optional, List

class EC2ProdConfig:
    """Parsed and validated configuration for EC2 Production Template"""
    
    def __init__(self, raw_config: Dict[str, Any]):
        params = raw_config.get('parameters', {}).get('aws', {}) or raw_config.get('parameters', {})
        self.vpc_mode = params.get('vpc_mode', 'new')
        self.vpc_id = params.get('vpc_id')
        self.vpc_cidr = params.get('vpc_cidr', '10.0.0.0/16')
        self.use_random_vpc_cidr = params.get('use_random_vpc_cidr', True)
        self.subnet_id = params.get('subnet_id')
        self.instance_name = params.get('instance_name', 'ec2-prod')
        self.ami_id = params.get('ami_id', 'resolve-ssm:/aws/service/ami-amazon-linux-latest/amzn2-ami-hvm-x86_64-gp2')
        self.instance_type = params.get('instance_type', 't3.small')
        self.enable_ssm = params.get('enable_ssm', True)
        self.key_name = params.get('key_name', '')
        self.security_group_ids = params.get('security_group_ids')
        self.volume_size = params.get('volume_size', 50)
        self.backup_retention = params.get('backup_retention', 7)
        self.ssh_access_ip = params.get('ssh_access_ip') or params.get('ssh_allowed_ips', [])
        self.region = params.get('region', 'us-east-1')
        self.environment = params.get('environment', 'prod')  # Default to 'prod' for production template
        self.tags = raw_config.get('tags', {})
        self.project_name = params.get('project_name') or params.get('projectName') or raw_config.get('project_name') or raw_config.get('projectName') or 'archie-ec2'
        self.config_preset = params.get('config_preset', params.get('configPreset', 'web-server'))

    @property
    def user_data(self) -> Optional[str]:
        """Load user data script for the web-server preset."""
        import datetime
        from pathlib import Path
        script_path = Path(__file__).parent / 'scripts' / 'web-server.sh'
        if not script_path.exists():
            return None
        content = script_path.read_text()
        env_name = 'prod' if self.environment in ('prod', 'production') else 'sandbox'
        try:
            return content.format(
                ENVIRONMENT=env_name,
                PROJECT_NAME=self.project_name,
                STACK_NAME=self.instance_name,
                TEMPLATE_NAME="EC2 Instance",
                REGION=self.region,
                TIMESTAMP=datetime.datetime.now().isoformat(),
                ALB_DNS='pending',
            )
        except (KeyError, ValueError):
            return content

    @staticmethod
    def get_config_schema() -> Dict[str, Any]:
        """Get JSON schema for UI configuration."""
        from provisioner.templates.shared.aws_schema import (
            get_project_env_schema,
            get_networking_schema,
            get_compute_selection_schema,
            get_security_connectivity_schema,
            get_observability_schema
        )
        schema = {
            **get_project_env_schema(order_offset=0),
            **get_networking_schema(allow_new=True, allow_existing=True, is_prod=True, order_offset=10),
            **get_compute_selection_schema(order_offset=70),
            **get_security_connectivity_schema(include_rdp=False, order_offset=130),
            **get_observability_schema(order_offset=200),
        }
        # Override config_preset with prod-appropriate options (no alb-backend or custom)
        schema["config_preset"] = {
            "type": "select",
            "title": "Platform Preset",
            "description": "Preconfigured software stack",
            "default": "web-server",
            "options": [
                {"label": "Web Server (PHP/HTML)", "value": "web-server"},
                {"label": "WordPress Stack", "value": "wordpress"},
                {"label": "MySQL Database", "value": "mysql"},
                {"label": "Node.js App", "value": "nodejs"}
            ],
            "group": "Compute Settings",
            "isEssential": True,
            "order": 75
        }
        return {
            "type": "object",
            "properties": schema,
            "required": ["project_name", "region"]
        }
