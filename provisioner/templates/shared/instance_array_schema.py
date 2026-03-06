"""
Instance Array Schema for Multi-Instance EC2 Deployments
Provides array-based schema for configuring multiple EC2 instances
"""
from typing import Dict, Any


def get_instance_array_schema(order_offset: int = 70) -> Dict[str, Any]:
    """
    Schema for multiple EC2 instance configurations.
    Returns array-type schema with repeatable instance blocks.
    
    Args:
        order_offset: Base order for field positioning
        
    Returns:
        Dict containing array schema for instances
    """
    return {
        "instances": {
            "type": "array",
            "title": "EC2 Instances",
            "description": "Configure one or more EC2 instances",
            "minItems": 1,
            "maxItems": 10,
            "default": [{}],  # Start with one empty instance config
            "items": {
                "type": "object",
                "title": "Instance Configuration",
                "properties": {
                    "instance_name": {
                        "type": "string",
                        "title": "Instance Name",
                        "description": "Unique identifier for this instance",
                        "placeholder": "Auto-Assign",
                        "order": 1
                    },
                    "instance_type": {
                        "type": "string",
                        "title": "Instance Type",
                        "description": "AWS instance type",
                        "enum": ["t3.micro", "t3.small", "t3.medium", "t4g.small", "t4g.medium"],
                        "enumLabels": {
                            "t3.micro": "t3.micro (Core / Cost)",
                            "t3.small": "t3.small (Standard)",
                            "t3.medium": "t3.medium (Standard plus)",
                            "t4g.small": "t4g.small (Graviton / Efficiency)",
                            "t4g.medium": "t4g.medium (Graviton plus)"
                        },
                        "default": "t3.micro",
                        "order": 2
                    },
                    "config_preset": {
                        "type": "string",
                        "title": "Platform Preset",
                        "description": "Preconfigured software stack",
                        "enum": ["web-server", "wordpress", "mysql", "nodejs", "alb-backend", "custom"],
                        "enumLabels": {
                            "web-server": "Web Server (PHP/HTML)",
                            "wordpress": "WordPress Stack",
                            "mysql": "MySQL Database",
                            "nodejs": "Node.js App",
                            "alb-backend": "ALB Target",
                            "custom": "Custom / Bare OS"
                        },
                        "default": "web-server",
                        "order": 3
                    },
                    "ami_os": {
                        "type": "string",
                        "title": "Operating System",
                        "description": "Base OS image",
                        "enum": ["amazon-linux-2", "ubuntu-22.04", "windows-2022", "custom"],
                        "enumLabels": {
                            "amazon-linux-2": "Amazon Linux 2 (Recommended)",
                            "ubuntu-22.04": "Ubuntu 22.04 LTS",
                            "windows-2022": "Windows Server 2022",
                            "custom": "Custom AMI ID"
                        },
                        "default": "amazon-linux-2",
                        "order": 4
                    },
                    "ami_id": {
                        "type": "string",
                        "title": "Custom AMI ID",
                        "description": "Specify a custom AWS AMI ID",
                        "placeholder": "ami-xxxxxxxxxxxxxxxxx",
                        "visibleIf": {"ami_os": "custom"},
                        "order": 5
                    },
                    "enable_ssm": {
                        "type": "boolean",
                        "title": "Enable Systems Manager",
                        "description": "Secure access without SSH",
                        "default": True,
                        "order": 6
                    }
                }
            },
            "group": "Compute Selection",
            "isEssential": True,
            "order": order_offset,
            "arrayItemTitle": "Instance {index}",  # Frontend hint for item titles
            "addButtonLabel": "Add Instance",
            "removeButtonLabel": "Remove"
        }
    }
