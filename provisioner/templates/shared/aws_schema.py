"""
Shared AWS Schema Library - CamelCase Version
Provides reusable UI configuration schemas for AWS templates.
"""
from typing import Dict, Any, List, Optional

def get_project_env_schema(order_offset: int = 0) -> Dict[str, Any]:
    """Standard Project and Environment fields"""
    return {
        "project_name": {
            "type": "string",
            "title": "Project Name",
            "description": "Project Name",
            "help_text": "Name of your project for resource tagging and tracking",
            "placeholder": "my-project",
            "group": "Essentials",
            "isEssential": True,
            "order": order_offset + 0
        },
        "region": {
            "type": "string",
            "title": "AWS Region",
            "description": "AWS Region",
            "default": "us-east-1",
            "enum": ["us-east-1", "us-east-2", "us-west-1", "us-west-2", "eu-west-1", "eu-central-1"],
            "group": "Essentials",
            "isEssential": True,
            "order": order_offset + 1
        },
    }

def get_networking_schema(allow_new: bool = True, allow_existing: bool = True, is_prod: bool = False, order_offset: int = 10) -> Dict[str, Any]:
    """
    Comprehensive Networking & Connectivity schema.
    
    Args:
        allow_new: Whether to allow creating a new VPC
        allow_existing: Whether to allow selecting an existing VPC
        is_prod: Whether to include production-grade features (3 AZs, Isolated subnets)
        order_offset: Base order for the fields
    """
    schema = {}
    
    # Header
    schema["vpc_header"] = {
        "type": "separator",
        "title": "VPC Configuration",
        "group": "Networking & Connectivity",
        "isEssential": True,
        "order": order_offset + 0
    }

    # Mode Selection (only if both are allowed)
    if allow_new and allow_existing:
        schema["vpc_mode"] = {
            "type": "select",
            "title": "VPC Selection",
            "description": "Deploy into a new or existing VPC",
            "default": "new",
            "options": [
                {"label": "Create New VPC", "value": "new"},
                {"label": "Use Existing VPC", "value": "existing"}
            ],
            "group": "Networking & Connectivity",
            "isEssential": False,  # Only show in custom view, default is greenfield only
            "order": order_offset + 1
        }

    # Existing VPC Fields
    if allow_existing:
        visible_if_existing = {"vpc_mode": "existing"} if allow_new else None
        schema["vpc_id"] = {
            "type": "string",
            "title": "Existing VPC ID",
            "description": "ID of the existing VPC",
            "placeholder": "vpc-xxxxxxxx",
            "group": "Networking & Connectivity",
            "visibleIf": visible_if_existing,
            "isEssential": False,  # Not essential since it's conditionally visible
            "order": order_offset + 2
        }
        schema["subnet_id"] = {
            "type": "string",
            "title": "Subnet ID",
            "description": "Select existing Subnet",
            "placeholder": "subnet-xxxxxxxx",
            "group": "Networking & Connectivity",
            "visibleIf": visible_if_existing,
            "isEssential": False,  # Not essential since it's conditionally visible
            "order": order_offset + 3
        }

    # New VPC Fields
    if allow_new:
        visible_if_new = {"vpc_mode": "new"} if allow_existing else None
        
        schema.update({
            "vpc_name": {
                "type": "string",
                "title": "VPC Name",
                "description": "Custom name for the new VPC",
                "placeholder": "Auto-generated",
                "group": "Networking & Connectivity",
                "visibleIf": visible_if_new,
                "isEssential": True,
                "order": order_offset + 10
            },
            "instance_tenancy": {
                "type": "select",
                "title": "VPC Tenancy",
                "description": "The allowed tenancy of instances launched into the VPC",
                "default": "default",
                "options": [
                    {"label": "Default", "value": "default"},
                    {"label": "Dedicated", "value": "dedicated"}
                ],
                "group": "Networking & Connectivity",
                "visibleIf": visible_if_new,
                "order": order_offset + 12
            },
            "cidr_block": {
                "type": "string",
                "title": "VPC CIDR Block",
                "description": "IPv4 CIDR block for the new VPC",
                "default": "",
                "placeholder": "Auto-Assign",
                "group": "Networking & Connectivity",
                "visibleIf": visible_if_new,
                "isEssential": True,
                "order": order_offset + 13
            },
            "dns_header": {
                "type": "separator",
                "title": "DNS Configuration",
                "group": "Networking & Connectivity",
                "visibleIf": visible_if_new,
                "isEssential": True,
                "order": order_offset + 59
            },
            "enable_dns_support": {
                "type": "boolean",
                "title": "Enable DNS Support",
                "description": "Allow DNS resolution",
                "default": True,
                "group": "Networking & Connectivity",
                "visibleIf": visible_if_new,
                "isEssential": True,
                "order": order_offset + 60
            },
            "enable_dns_hostnames": {
                "type": "boolean",
                "title": "Enable DNS Hostnames",
                "description": "Assign public hostnames",
                "default": True,
                "group": "Networking & Connectivity",
                "visibleIf": visible_if_new,
                "isEssential": True,
                "order": order_offset + 61
            },
            "subnet_header": {
                "type": "separator",
                "title": "Subnet Configuration",
                "group": "Networking & Connectivity",
                "visibleIf": visible_if_new,
                "order": order_offset + 19
            },
            # --- Zone 1 ---
            "public_subnet_1_cidr": {
                "type": "string",
                "title": "Public Subnet 1 CIDR",
                "placeholder": "e.g. 10.0.1.0/24",
                "group": "Networking & Connectivity",
                "visibleIf": visible_if_new,
                "order": order_offset + 20
            },
            "az_1": {
                "type": "string",
                "title": "Availability Zone 1",
                "placeholder": "e.g. us-east-1a",
                "group": "Networking & Connectivity",
                "visibleIf": visible_if_new,
                "order": order_offset + 21
            },
            "private_subnet_1_cidr": {
                "type": "string",
                "title": "Private Subnet 1 CIDR",
                "placeholder": "e.g. 10.0.11.0/24",
                "group": "Networking & Connectivity",
                "visibleIf": visible_if_new,
                "order": order_offset + 22
            }
        })

        if is_prod:
            schema["isolated_subnet_1_cidr"] = {
                "type": "string",
                "title": "Isolated Subnet 1 CIDR",
                "placeholder": "e.g. 10.0.21.0/24",
                "group": "Networking & Connectivity",
                "visibleIf": visible_if_new,
                "order": order_offset + 23
            }

        schema.update({
            "zone_2_separator": {
                "type": "separator",
                "title": "Secondary Zone Configuration",
                "group": "Networking & Connectivity",
                "visibleIf": visible_if_new,
                "order": order_offset + 24
            },
            "public_subnet_2_cidr": {
                "type": "string",
                "title": "Public Subnet 2 CIDR",
                "placeholder": "e.g. 10.0.2.0/24",
                "group": "Networking & Connectivity",
                "visibleIf": visible_if_new,
                "order": order_offset + 25
            },
            "az_2": {
                "type": "string",
                "title": "Availability Zone 2",
                "placeholder": "e.g. us-east-1b",
                "group": "Networking & Connectivity",
                "visibleIf": visible_if_new,
                "order": order_offset + 26
            },
            "private_subnet_2_cidr": {
                "type": "string",
                "title": "Private Subnet 2 CIDR",
                "placeholder": "e.g. 10.0.12.0/24",
                "group": "Networking & Connectivity",
                "visibleIf": visible_if_new,
                "order": order_offset + 27
            }
        })

        if is_prod:
            schema["isolated_subnet_2_cidr"] = {
                "type": "string",
                "title": "Isolated Subnet 2 CIDR",
                "placeholder": "e.g. 10.0.22.0/24",
                "group": "Networking & Connectivity",
                "visibleIf": visible_if_new,
                "order": order_offset + 28
            }
            schema.update({
                "zone_3_separator": {
                    "type": "separator",
                    "title": "Tertiary Zone Configuration",
                    "group": "Networking & Connectivity",
                    "visibleIf": visible_if_new,
                    "order": order_offset + 29
                },
                "public_subnet_3_cidr": {
                    "type": "string",
                    "title": "Public Subnet 3 CIDR",
                    "placeholder": "e.g. 10.0.3.0/24",
                    "group": "Networking & Connectivity",
                    "visibleIf": visible_if_new,
                    "order": order_offset + 30
                },
                "az_3": {
                    "type": "string",
                    "title": "Availability Zone 3",
                    "placeholder": "e.g. us-east-1c",
                    "group": "Networking & Connectivity",
                    "visibleIf": visible_if_new,
                    "order": order_offset + 31
                },
                "private_subnet_3_cidr": {
                    "type": "string",
                    "title": "Private Subnet 3 CIDR",
                    "placeholder": "e.g. 10.0.13.0/24",
                    "group": "Networking & Connectivity",
                    "visibleIf": visible_if_new,
                    "order": order_offset + 32
                },
                "isolated_subnet_3_cidr": {
                    "type": "string",
                    "title": "Isolated Subnet 3 CIDR",
                    "placeholder": "e.g. 10.0.23.0/24",
                    "group": "Networking & Connectivity",
                    "visibleIf": visible_if_new,
                    "order": order_offset + 33
                }
            })

        schema.update({
            "nat_header": {
                "type": "separator",
                "title": "NAT Gateway Configuration",
                "group": "Networking & Connectivity",
                "visibleIf": visible_if_new,
                "isEssential": True,
                "order": order_offset + 49
            },
            "enable_nat_gateway": {
                "type": "boolean",
                "title": "Provision NAT Gateway",
                "description": "Provide internet access to private subnets",
                "default": True,
                "group": "Networking & Connectivity",
                "visibleIf": visible_if_new,
                "isEssential": True,
                "order": order_offset + 50
            },
            "nat_gateway_count": {
                "type": "number",
                "title": "NAT Gateway Count",
                "description": "1 for cost-optimization, 2-3 for higher availability",
                "default": 3 if is_prod else 1,
                "options": [
                    {"label": "Single (Cost Optimized)", "value": 1},
                    {"label": "Double (High Availability)", "value": 2} if not is_prod else {"label": "Triple (Production Grade)", "value": 3}
                ],
                "group": "Networking & Connectivity",
                "visibleIf": {"enable_nat_gateway": True},
                "order": order_offset + 51
            }
        })
        
    return schema

def get_vpc_selection_schema(allow_new: bool = True, allow_existing: bool = True) -> Dict[str, Any]:
    """Compatibility shim for old vpc selection schema"""
    return get_networking_schema(allow_new=allow_new, allow_existing=allow_existing)

def get_compute_selection_schema(order_offset: int = 70) -> Dict[str, Any]:
    """Standard Compute Selection fields including instance type, OS, and presets"""
    return {
        "compute_header": {
            "type": "separator",
            "title": "Compute Configuration",
            "group": "Compute Selection",
            "isEssential": True,
            "order": order_offset + 0
        },
        "instance_name": {
            "type": "string",
            "title": "Instance Name",
            "description": "Unique identifier for the instance",
            "placeholder": "Auto-Assign",
            "group": "Compute Selection",
            "isEssential": True,
            "order": order_offset + 1
        },
        "instance_type": {
            "type": "string",
            "title": "Instance Type",
            "description": "Standard non-prod families",
            "enum": ["t3.micro", "t3.small", "t3.medium", "t4g.small", "t4g.medium"],
            "enumLabels": {
                "t3.micro": "t3.micro (Core / Cost)",
                "t3.small": "t3.small (Standard)",
                "t3.medium": "t3.medium (Standard plus)",
                "t4g.small": "t4g.small (Graviton / Efficiency)",
                "t4g.medium": "t4g.medium (Graviton plus)"
            },
            "default": "t3.micro",
            "group": "Compute Selection",
            "isEssential": True,
            "order": order_offset + 2
        },
        "preset_banner": {
            "type": "info",
            "title": "Configuration Presets",
            "description": "Presets automatically configure security groups, ports, and installation scripts for common stacks. Select 'Custom' to manually define everything.",
            "group": "Compute Selection",
            "isEssential": True,
            "order": order_offset + 3
        },
        "cost_banner": {
            "type": "info",
            "title": "Cost Optimization",
            "description": "For non-prod environments, we recommend using 't3' or 't4g' burstable instances to keep costs low while maintaining performance for bursty workloads.",
            "group": "Compute Selection",
            "isEssential": True,
            "order": order_offset + 4
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
            "group": "Compute Selection",
            "isEssential": True,
            "order": order_offset + 5
        },
        "ami_os": {
            "type": "string",
            "title": "Operating System",
            "description": "Base OS image recommendation",
            "enum": ["amazon-linux-2", "ubuntu-22.04", "windows-2022", "custom"],
            "enumLabels": {
                "amazon-linux-2": "Amazon Linux 2 (Recommended)",
                "ubuntu-22.04": "Ubuntu 22.04 LTS",
                "windows-2022": "Windows Server 2022",
                "custom": "Custom AMI ID"
            },
            "default": "amazon-linux-2",
            "group": "Compute Selection",
            "isEssential": True,
            "order": order_offset + 6
        },
        "ami_id": {
            "type": "string",
            "title": "Custom AMI ID",
            "description": "Specify a custom AWS AMI ID",
            "placeholder": "ami-xxxxxxxxxxxxxxxxx",
            "visibleIf": {"ami_os": "custom"},
            "group": "Compute Selection",
            "order": order_offset + 7
        },
        "key_name": {
            "type": "string",
            "title": "SSH Key Pair",
            "description": "Existing key pair for SSH",
            "group": "Compute Selection",
            "order": order_offset + 8
        },
        "enable_ssm": {
            "type": "boolean",
            "title": "Enable Systems Manager",
            "description": "Secure access without SSH",
            "default": True,
            "group": "Compute Selection",
            "isEssential": True,
            "order": order_offset + 9
        }
    }

def get_security_connectivity_schema(include_rdp: bool = False, order_offset: int = 130) -> Dict[str, Any]:
    """Standard Security & Connectivity fields used across VPC and Compute templates"""
    schema = {
        "security_header": {
            "type": "separator",
            "title": "Security Group Configuration",
            "group": "Security & Connectivity",
            "isEssential": True,
            "order": order_offset + 5
        },
        "ssh_mode": {
            "type": "select",
            "title": "Access Mode",
            "description": "Choose between secure SSM access or emergency SSH/RDP",
            "default": "ssm-only",
            "options": [
                {"label": "Standard (SSM Only)", "value": "ssm-only"},
                {"label": "Advanced (Enable SSH/RDP)", "value": "enabled"}
            ],
            "group": "Security & Connectivity",
            "isEssential": False,
            "order": order_offset + 10,
            "help_text": "Standard Security Policy\nSSH and RDP ports remain closed. Secure management via AWS Systems Manager (SSM) is enabled by default."
        },
        "ssh_access_ip": {
            "type": "string",
            "title": "Admin Access IP (SSH/RDP)",
            "description": "IP address or CIDR block (required for advanced mode)",
            "placeholder": "e.g. 203.0.113.25/32",
            "group": "Security & Connectivity",
            "visibleIf": {"ssh_mode": "enabled"},
            "isEssential": True,
            "order": order_offset + 11
        }
    }

    if include_rdp:
        # Add RDP mode selector and conditional IP field for Windows
        schema["ssh_mode"]["visibleIf"] = {"ami_os": {"in": ["amazon-linux-2", "ubuntu-22.04", "custom"]}}
        schema["rdp_mode"] = {
            "type": "select",
            "title": "Access Mode (RDP)",
            "description": "Choose between secure SSM access or emergency RDP",
            "default": "ssm-only",
            "options": [
                {"label": "Standard (SSM Only)", "value": "ssm-only"},
                {"label": "Advanced (Enable RDP)", "value": "enabled"}
            ],
            "visibleIf": {"ami_os": "windows-2022"},
            "group": "Security & Connectivity",
            "isEssential": False,
            "order": order_offset + 10,
            "help_text": "Standard Security Policy\nRDP ports remain closed. Secure management via AWS Systems Manager (SSM) is enabled by default."
        }
        schema["rdp_access_ip"] = {
            "type": "string",
            "title": "RDP Access IP",
            "description": "IP address or CIDR block (required for advanced mode)",
            "placeholder": "e.g. 203.0.113.25/32",
            "visibleIf": {"rdp_mode": "enabled"},
            "group": "Security & Connectivity",
            "isEssential": True,
            "order": order_offset + 11
        }

    schema.update({
        "endpoint_header": {
            "type": "separator",
            "title": "Endpoint Configuration",
            "group": "Security & Connectivity",
            "isEssential": True,
            "order": order_offset + 20
        },
        "enable_ssm_endpoints": {
            "type": "boolean",
            "title": "Enable SSM Endpoints",
            "description": "Interface Endpoints for secure management",
            "default": True,
            "help_text": "Required for secure instance access without SSH/IGW.",
            "group": "Security & Connectivity",
            "isEssential": True,
            "order": order_offset + 21
        },
        "enable_s3_endpoint": {
            "type": "boolean",
            "title": "Enable S3 Endpoint",
            "description": "Private gateway access to S3",
            "default": True,
            "group": "Security & Connectivity",
            "isEssential": True,
            "order": order_offset + 22
        },
        "enable_dynamodb_endpoint": {
            "type": "boolean",
            "title": "Enable DynamoDB Endpoint",
            "description": "Private gateway access to DynamoDB",
            "default": True,
            "group": "Security & Connectivity",
            "isEssential": True,
            "order": order_offset + 23
        },
        "port_header": {
            "type": "separator",
            "title": "Custom Port Overrides",
            "group": "Security & Connectivity",
            "isEssential": True,
            "order": order_offset + 30
        },
        "web_port": {
            "type": "number",
            "title": "Web Traffic Port",
            "description": "Standard port for web traffic (HTTP)",
            "default": 80,
            "group": "Security & Connectivity",
            "isEssential": True,
            "order": order_offset + 31
        },
        "app_port": {
            "type": "number",
            "title": "Application Port",
            "description": "Port for internal application services",
            "default": 8080,
            "group": "Security & Connectivity",
            "isEssential": True,
            "order": order_offset + 32
        },
        "db_port": {
            "type": "number",
            "title": "Database Port",
            "description": "Port for database connections",
            "default": 5432,
            "group": "Security & Connectivity",
            "isEssential": True,
            "order": order_offset + 33
        }
    })
    
    return schema

def get_observability_schema(order_offset: int = 200) -> Dict[str, Any]:
    """Standard Observability fields (Flow Logs, Monitoring)"""
    return {
        "flow_logs_header": {
            "type": "separator",
            "title": "Flow Logs Configuration",
            "group": "Observability",
            "isEssential": True,
            "order": order_offset + 0
        },
        "enable_flow_logs": {
            "type": "boolean",
            "title": "Enable Flow Logs",
            "description": "Capture IP traffic information",
            "default": True,
            "group": "Observability",
            "isEssential": True,
            "order": order_offset + 1
        },
        "log_destination_type": {
            "type": "select",
            "title": "Flow Log Destination",
            "description": "Where to store flow logs",
            "default": "cloud-watch-logs",
            "options": [
                {"label": "CloudWatch Logs", "value": "cloud-watch-logs"},
                {"label": "S3 Bucket", "value": "s3"}
            ],
            "group": "Observability",
            "visibleIf": {"enable_flow_logs": True},
            "order": order_offset + 2
        },
        "flow_log_retention": {
            "type": "number",
            "title": "Log Retention (Days)",
            "description": "How long to keep flow logs",
            "default": 7,
            "group": "Observability",
            "visibleIf": {"enable_flow_logs": True},
            "order": order_offset + 3
        }
    }

def get_database_selection_schema(engine: str = "postgres", order_offset: int = 80) -> Dict[str, Any]:
    """Standard Database Selection fields"""
    return {
        "db_header": {
            "type": "separator",
            "title": "Database Configuration",
            "group": "Database Settings",
            "isEssential": True,
            "order": order_offset + 0
        },
        "dbName": {
            "type": "string",
            "title": "Database Name",
            "description": "Primary database name",
            "default": "mydb",
            "group": "Database Settings",
            "isEssential": True,
            "order": order_offset + 1
        },
        "dbUsername": {
            "type": "string",
            "title": "Master Username",
            "description": "Database administrator username",
            "default": "postgres" if engine == "postgres" else "admin",
            "group": "Database Settings",
            "isEssential": True,
            "order": order_offset + 2
        },
        "engineVersion": {
            "type": "string",
            "title": "Engine Version",
            "description": f"Version of {engine}",
            "default": "15" if engine == "postgres" else "8.0",
            "group": "Database Settings",
            "order": order_offset + 3
        },
        "instanceClass": {
            "type": "string",
            "title": "Instance Class",
            "description": "Compute and memory capacity",
            "default": "db.t3.micro",
            "enum": ["db.t3.micro", "db.t3.small", "db.t3.medium", "db.t3.large", "db.m5.large"],
            "group": "Database Settings",
            "isEssential": True,
            "order": order_offset + 4
        },
        "allocatedStorage": {
            "type": "number",
            "title": "Allocated Storage (GB)",
            "description": "Initial storage capacity",
            "default": 20,
            "group": "Database Settings",
            "order": order_offset + 5
        },
        "maxAllocatedStorage": {
            "type": "number",
            "title": "Max Storage (GB)",
            "description": "Auto-scaling storage limit",
            "default": 100,
            "group": "Database Settings",
            "order": order_offset + 6
        },
        "backupRetentionDays": {
            "type": "number",
            "title": "Backup Retention (Days)",
            "description": "Number of days to keep backups",
            "default": 3,
            "group": "Database Settings",
            "order": order_offset + 7
        }
    }

def get_multi_instance_compute_schema(order_offset: int = 70) -> Dict[str, Any]:
    """
    Multi-Instance Compute Selection schema.
    Wraps instance configuration in an array for defining 1-N instances.
    """
    # Reuse the single instance schema items for the array configuration
    single_instance = get_compute_selection_schema(order_offset=0)
    
    # Remove header from the items as it belongs to the parent group
    if "compute_header" in single_instance:
        del single_instance["compute_header"]

    return {
        "compute_header": {
            "type": "separator",
            "title": "Compute Configuration",
            "group": "Compute Selection",
            "isEssential": True,
            "order": order_offset + 0
        },
        "instances": {
            "type": "array",
            "title": "EC2 Instances",
            "description": "Configure multiple instances",
            "minItems": 1,
            "maxItems": 10,
            "default": [{}],
            "group": "Compute Selection",
            "addButtonLabel": "Add Instance",
            "arrayItemTitle": "Instance {index}",
            "isEssential": True,
            "order": order_offset + 1,
            "items": {
                "type": "object",
                "properties": single_instance
            }
        }
    }

def get_cdn_storage_schema(order_offset: int = 30) -> Dict[str, Any]:
    """
    CDN and Storage configuration schema for CloudFront/S3 templates.
    
    Args:
        order_offset: Base order for the fields
    """
    return {
        "cdn_header": {
            "type": "separator",
            "title": "Content Delivery Configuration",
            "group": "Networking & Connectivity",
            "isEssential": True,
            "order": order_offset + 0
        },
        "cloudfront": {
            "type": "object",
            "title": "CloudFront Distribution",
            "order": order_offset + 1,
            "properties": {
                "enabled": {
                    "type": "boolean",
                    "title": "Distribution Enabled",
                    "description": "Whether the CloudFront distribution is enabled",
                    "default": True
                },
                "price_class": {
                    "type": "string",
                    "title": "Price Class",
                    "description": "CloudFront price class determining global edge locations",
                    "enum": ["PriceClass_100", "PriceClass_200", "PriceClass_All"],
                    "default": "PriceClass_100"
                },
                "default_root_object": {
                    "type": "string",
                    "title": "Default Root Object",
                    "description": "Default file to serve for root requests",
                    "default": "index.html"
                }
            }
        },
        "storage_header": {
            "type": "separator",
            "title": "Storage Configuration",
            "group": "Networking & Connectivity",
            "isEssential": True,
            "order": order_offset + 10
        },
        "storage_objects": {
            "type": "object",
            "title": "Static Files",
            "description": "Configuration for static files uploaded to storage",
            "order": order_offset + 11,
            "properties": {
                "files": {
                    "type": "array",
                    "title": "Static Files",
                    "description": "List of static files to upload",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "title": "File Name"
                            },
                            "source": {
                                "type": "string",
                                "title": "Source Path"
                            },
                            "content_type": {
                                "type": "string",
                                "title": "Content Type"
                            },
                            "description": {
                                "type": "string",
                                "title": "Description"
                            }
                        }
                    },
                    "default": [
                        {
                            "name": "index.html",
                            "source": "index.html",
                            "content_type": "text/html",
                            "description": "Main page"
                        },
                        {
                            "name": "styles.css",
                            "source": "styles.css",
                            "content_type": "text/css",
                            "description": "Stylesheet"
                        }
                    ]
                }
            }
        },
        "bucket": {
            "type": "object",
            "title": "Storage Bucket",
            "order": order_offset + 12,
            "properties": {
                "versioning": {
                    "type": "boolean",
                    "title": "Versioning Enabled",
                    "description": "Enable storage bucket versioning",
                    "default": False
                },
                "force_destroy": {
                    "type": "boolean",
                    "title": "Force Destroy",
                    "description": "Allow bucket deletion even if not empty",
                    "default": True
                }
            }
        },
        "website": {
            "type": "object",
            "title": "Website Hosting",
            "order": order_offset + 13,
            "properties": {
                "index_document": {
                    "type": "string",
                    "title": "Index Document",
                    "description": "Default file for directory requests",
                    "default": "index.html"
                },
                "error_document": {
                    "type": "string",
                    "title": "Error Document",
                    "description": "Error page for 404 responses",
                    "default": "error.html"
                }
            }
        }
    }
