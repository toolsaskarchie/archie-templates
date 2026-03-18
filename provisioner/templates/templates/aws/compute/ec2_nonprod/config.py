"""
Configuration parser for EC2 Non-Prod Template
"""

import datetime
from typing import Dict, Any, Optional, List

class EC2NonProdConfig:
    """Parsed and validated configuration for EC2 Non-Prod Template"""

    # Preset configurations - now pointing to external scripts in the 'scripts' folder
    PRESETS = {
        'web-server': {
            'instance_type': 't3.micro',
            'ports': [80, 443],
            'script': 'web-server.sh',
            'is_template': True
        },
        'wordpress': {
            'instance_type': 't3.small',
            'ports': [80, 443],
            'script': 'wordpress.sh',
            'is_template': False
        },
        'mysql': {
            'instance_type': 't3.small',
            'ports': [3306],
            'script': 'mysql.sh',
            'is_template': False
        },
        'nodejs': {
            'instance_type': 't3.micro',
            'ports': [3000],
            'script': 'nodejs.sh',
            'is_template': False
        },
        'alb-backend': {
            'instance_type': 't3.micro',
            'ports': [80, 443],
            'script': 'alb-backend.sh',
            'is_template': True
        }
    }

    def _load_script(self, filename: str) -> str:
        """Load a script from the scripts directory."""
        from pathlib import Path
        script_path = Path(__file__).parent / 'scripts' / filename
        try:
            with open(script_path, 'r') as f:
                return f.read()
        except Exception as e:
            print(f"Error loading script {filename}: {e}")
            return f"#!/bin/bash\necho 'Error loading setup script'"

    def __init__(self, raw_config: Dict[str, Any]):
        self.raw_config = raw_config
        self.parameters = self.raw_config.get('parameters', {}).get('aws', {})
        self.environment = 'nonprod'
        self.region = self.raw_config.get('region', 'us-east-1')
        self.tags = self.raw_config.get('tags', {})

    def get_parameter(self, key: str, default: Any = None) -> Any:
        """Get a parameter from the configuration."""
        return self.parameters.get(key, default)

    @property
    def project_name(self) -> str:
        """Get project name from config."""
        return (
            self.get_parameter('projectName') or
            self.get_parameter('project_name') or
            self.raw_config.get('projectName') or
            self.raw_config.get('project_name') or
            'archie-ec2'
        )

    @property
    def config_preset(self) -> str:
        """Get EC2 configuration preset, defaults to 'web-server'."""
        return (
            self.get_parameter('configPreset') or 
            self.get_parameter('config_preset') or 
            'web-server'
        )

    @property
    def vpc_mode(self) -> str:
        """Get VPC provisioning mode, defaults to 'new'."""
        return (
            self.get_parameter('vpcMode') or 
            self.get_parameter('vpc_mode') or 
            'new'
        )

    @property
    def vpc_id(self) -> Optional[str]:
        """Get existing VPC ID if specified."""
        return self.get_parameter('vpcId') or self.get_parameter('vpc_id')

    @property
    def vpc_name(self) -> Optional[str]:
        """Get VPC name if specified, otherwise will be auto-generated."""
        return self.get_parameter('vpc_name') or self.get_parameter('vpcName')

    @property
    def vpc_cidr(self) -> str:
        """DEPRECATED: Use cidr_block instead."""
        return self.cidr_block

    @property
    def cidr_block(self) -> str:
        """Get VPC CIDR block, defaults to 'random'."""
        return (
            self.get_parameter('cidr_block') or 
            self.get_parameter('cidrBlock') or 
            self.get_parameter('vpc_cidr') or 
            self.get_parameter('vpcCidr') or 
            'random'
        )

    @property
    def use_custom_cidr(self) -> bool:
        """Whether to use a custom VPC CIDR, defaults to False."""
        val = self.get_parameter('use_custom_cidr')
        if val is None:
            val = self.get_parameter('useCustomCidr')
        if val is None:
            # Check legacy field as fallback
            use_random = self.get_parameter('use_random_vpc_cidr')
            if use_random is False: return True # If random was disabled, they intended custom
            return False
        return val

    @property
    def use_random_vpc_cidr(self) -> bool:
        """DEPRECATED: Use not use_custom_cidr instead."""
        return not self.use_custom_cidr

    @property
    def subnet_id(self) -> Optional[str]:
        """Get existing subnet ID if specified."""
        return self.get_parameter('subnetId') or self.get_parameter('subnet_id')

    @property
    def enable_nat_gateway(self) -> bool:
        """Whether to enable NAT gateway, defaults to True."""
        val = self.get_parameter('enableNatGateway')
        if val is None:
            val = self.get_parameter('enable_nat_gateway')
        if val is None:
            return True
        return val

    @property
    def enable_flow_logs(self) -> bool:
        """Whether to enable VPC flow logs, defaults to True."""
        val = self.get_parameter('enableFlowLogs')
        if val is None:
            val = self.get_parameter('enable_flow_logs')
        if val is None:
            return True
        return val

    @property
    def enable_s3_endpoint(self) -> bool:
        """Whether to enable S3 VPC endpoint, defaults to True."""
        val = self.get_parameter('enableS3Endpoint')
        if val is None:
            val = self.get_parameter('enable_s3_endpoint')
        if val is None:
            return True
        return val

    @property
    def enable_dynamodb_endpoint(self) -> bool:
        """Whether to enable DynamoDB VPC endpoint, defaults to True."""
        val = self.get_parameter('enableDynamoDbEndpoint')
        if val is None:
            val = self.get_parameter('enable_dynamodb_endpoint')
        if val is None:
            return True
        return val

    @property
    def instance_name(self) -> str:
        """Get instance name, defaults to empty string if auto."""
        return self.get_parameter('instance_name') or ''

    @property
    def enable_ssm(self) -> bool:
        """Whether to enable AWS Systems Manager, defaults to True."""
        val = self.get_parameter('enableSsm')
        if val is None:
            val = self.get_parameter('enable_ssm')
        if val is None:
            return True
        return val

    @property
    def enable_ssm_endpoints(self) -> bool:
        """Whether to enable SSM interface endpoints, defaults to True."""
        return self.get_parameter('enable_ssm_endpoints', True)

    @property
    def enable_s3_endpoint(self) -> bool:
        """Whether to enable S3 gateway endpoint, defaults to True."""
        return self.get_parameter('enable_s3_endpoint', True)

    @property
    def enable_dynamodb_endpoint(self) -> bool:
        """Whether to enable DynamoDB gateway endpoint, defaults to True."""
        return self.get_parameter('enable_dynamodb_endpoint', True)

    @property
    def enable_ssh_access(self) -> bool:
        """Whether to enable SSH access security group, defaults to False."""
        val = self.get_parameter('enable_ssh_access')
        if val is None:
            val = self.get_parameter('enableSshAccess')
        if val is None:
            return False
        return val

    @property
    def instance_tenancy(self) -> str:
        """Get VPC instance tenancy, defaults to 'default'."""
        return self.get_parameter('instance_tenancy', 'default')

    @property
    def enable_dns_support(self) -> bool:
        """Whether to enable DNS support for VPC, defaults to True."""
        val = self.get_parameter('enable_dns_support')
        if val is None:
            val = self.get_parameter('enableDnsSupport')
        if val is None:
            return True
        return val

    @property
    def enable_dns_hostnames(self) -> bool:
        """Whether to enable DNS hostnames for VPC, defaults to True."""
        val = self.get_parameter('enable_dns_hostnames')
        if val is None:
            val = self.get_parameter('enableDnsHostnames')
        if val is None:
            return True
        return val

    @property
    def public_subnet_1_cidr(self) -> Optional[str]:
        return self.get_parameter('public_subnet_1_cidr')

    @property
    def public_subnet_2_cidr(self) -> Optional[str]:
        return self.get_parameter('public_subnet_2_cidr')

    @property
    def private_subnet_1_cidr(self) -> Optional[str]:
        return self.get_parameter('private_subnet_1_cidr')

    @property
    def private_subnet_2_cidr(self) -> Optional[str]:
        return self.get_parameter('private_subnet_2_cidr')

    @property
    def az_1(self) -> str:
        """Get availability zone 1, defaults to '{region}a'."""
        az = self.get_parameter('az_1')
        if az is None or az == '':
            return f'{self.region}a'
        return az

    @property
    def az_2(self) -> str:
        """Get availability zone 2, defaults to '{region}b'."""
        az = self.get_parameter('az_2')
        if az is None or az == '':
            return f'{self.region}b'
        return az

    @property
    def nat_gateway_count(self) -> int:
        return int(self.get_parameter('nat_gateway_count', 1))

    @property
    def flow_log_retention(self) -> int:
        return int(self.get_parameter('flow_log_retention', 7))

    @property
    def web_port(self) -> int:
        """Standard port for web traffic, defaults to 80."""
        return int(self.get_parameter('web_port', 80))

    @property
    def app_port(self) -> int:
        """Port for internal application services, defaults to 8080."""
        return int(self.get_parameter('app_port', 8080))

    @property
    def db_port(self) -> int:
        """Port for database connections, defaults to 5432."""
        return int(self.get_parameter('db_port', 5432))

    @property
    def log_destination_type(self) -> str:
        """Where to store flow logs, defaults to 'cloud-watch-logs'."""
        return self.get_parameter('log_destination_type', 'cloud-watch-logs')

    @property
    def ssh_access_ip(self) -> Optional[str]:
        """Get SSH access IP address."""
        return self.get_parameter('ssh_access_ip') or self.get_parameter('ssh_allowed_ips')

    @property
    def rdp_access_ip(self) -> Optional[str]:
        """Get RDP access IP address."""
        return self.get_parameter('rdp_access_ip')

    @property
    def key_name(self) -> Optional[str]:
        """Get EC2 key pair name."""
        return self.get_parameter('keyName') or self.get_parameter('key_name')

    @property
    def security_group_ids(self) -> List[str]:
        """Get additional security group IDs."""
        return self.get_parameter('securityGroupIds') or self.get_parameter('security_group_ids', [])

    @property
    def ssh_allowed_ips(self) -> List[str]:
        """Get allowed IP ranges for SSH access."""
        return self.get_parameter('sshAllowedIps') or self.get_parameter('ssh_allowed_ips', [])

    @property
    def availability_zones(self) -> List[str]:
        """Get availability zones for the VPC."""
        azs = self.get_parameter('availabilityZones') or self.get_parameter('availability_zones', [f"{self.region}a", f"{self.region}b"])
        if isinstance(azs, str):
            return [f"{self.region}a", f"{self.region}b"]
        return [
            az.split('(')[0].strip() if isinstance(az, str) and '(' in az else az 
            for az in azs
        ]

    @property
    def instance_type(self) -> str:
        """Get EC2 instance type with preset override."""
        user_type = self.get_parameter('instanceType') or self.get_parameter('instance_type')
        if (not user_type or self.config_preset != 'custom') and self.config_preset in self.PRESETS:
            return self.PRESETS[self.config_preset]['instance_type']
        return user_type or 't3.micro'

    @property
    def ami_os(self) -> str:
        """Get AMI OS selection, defaults to 'amazon-linux-2'."""
        return self.get_parameter('ami_os', 'amazon-linux-2')

    @property
    def ami_id(self) -> str:
        """Get AMI ID, resolved from OS or custom value."""
        os_paths = {
            'amazon-linux-2': 'resolve-ssm:/aws/service/ami-amazon-linux-latest/amzn2-ami-hvm-x86_64-gp2',
            'ubuntu-22.04': 'resolve-ssm:/aws/service/canonical/ubuntu/server/22.04-LTS/amd64/server/stable/current',
            'windows-2022': 'resolve-ssm:/aws/service/ami-windows-latest/Windows_Server-2022-English-Full-Base'
        }
        if self.ami_os in os_paths:
            return os_paths[self.ami_os]
        return self.get_parameter('ami_id') or os_paths['amazon-linux-2']

    @property
    def preset_ports(self) -> List[int]:
        """Get open ports for the selected preset."""
        if self.config_preset in self.PRESETS:
            return self.PRESETS[self.config_preset].get('ports', [])
        return []

    @property
    def user_data(self) -> Optional[str]:
        """Get processed user data for the selected preset."""
        # Check if user provided custom user data
        custom_user_data = (
            self.get_parameter('userDataTemplate') or 
            self.get_parameter('user_data_template') or 
            self.get_parameter('userData') or 
            self.get_parameter('user_data')
        )
        if custom_user_data:
            return custom_user_data

        if self.config_preset not in self.PRESETS:
            return None

        preset = self.PRESETS[self.config_preset]
        script_content = self._load_script(preset['script'])
        
        # If it's a template, format it with deployment metadata
        if preset.get('is_template'):
            env_name = 'sandbox' if self.environment in ['nonprod', 'dev', 'development'] else 'prod'
            stack_name = self.get_parameter('stackName') or self.get_parameter('stack_name') or self.instance_name
            alb_dns = self.get_parameter('albDns') or self.get_parameter('alb_dns', 'pending')
            
            try:
                # Note: The external scripts use single curly braces for Python format()
                return script_content.format(
                    ENVIRONMENT=env_name,
                    PROJECT_NAME=self.project_name,
                    STACK_NAME=stack_name,
                    TEMPLATE_NAME="EC2 Web Server",
                    REGION=self.region,
                    TIMESTAMP=datetime.datetime.now().isoformat(),
                    ALB_DNS=alb_dns
                )
            except (KeyError, ValueError) as e:
                print(f"Bypassing formatting for {preset['script']} due to error: {e}")
                return script_content
        
        return script_content

    @property
    def instances(self) -> List[Dict[str, Any]]:
        """
        Get array of instance configurations.
        Supports both legacy single-instance and new multi-instance modes.
        
        Returns:
            List of instance configuration dicts
        """
        # Check if using new array-based schema
        instances_array = self.get_parameter('instances')
        
        if instances_array and isinstance(instances_array, list):
            # New multi-instance mode
            return instances_array
        
        # Check for instance_count (1-N mode)
        count = self.get_parameter('instance_count')
        if count is not None and isinstance(count, (int, str)):
            try:
                count = int(count)
                if count > 1:
                    # Generate clones for multi-instance support
                    return [{
                        'instance_name': f"{self.instance_name}-{i:02d}" if self.instance_name else "auto-assign",
                        'instance_type': self.instance_type,
                        'config_preset': self.config_preset,
                        'ami_os': self.ami_os,
                        'ami_id': self.ami_id if self.ami_os == 'custom' else None,
                        'enable_ssm': self.enable_ssm
                    } for i in range(1, count + 1)]
            except (ValueError, TypeError):
                pass

        # Legacy single-instance mode - create array with single item
        return [{
            'instance_name': self.instance_name,
            'instance_type': self.instance_type,
            'config_preset': self.config_preset,
            'ami_os': self.ami_os,
            'ami_id': self.ami_id if self.ami_os == 'custom' else None,
            'enable_ssm': self.enable_ssm
        }]

    @property
    def instance_count(self) -> int:
        """Number of EC2 instances to create, defaults to 1."""
        val = self.get_parameter('instance_count')
        if val is not None:
            try:
                return int(val)
            except (ValueError, TypeError):
                pass
        return 1

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        """Get configuration schema for the UI"""
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
                # --- Compute ---
                "config_preset": {
                    "type": "string",
                    "title": "Configuration Preset",
                    "description": "Pre-configured setup for common workloads",
                    "default": "web-server",
                    "enum": ["web-server", "wordpress", "mysql", "nodejs", "alb-backend"],
                    "group": "Compute",
                    "isEssential": True,
                    "order": 10
                },
                "instance_type": {
                    "type": "string",
                    "title": "Instance Type",
                    "description": "EC2 instance size",
                    "default": "t3.micro",
                    "enum": ["t3.micro", "t3.small", "t3.medium", "t3.large", "t3.xlarge"],
                    "group": "Compute",
                    "isEssential": True,
                    "order": 11
                },
                "ami_os": {
                    "type": "string",
                    "title": "Operating System",
                    "description": "AMI operating system",
                    "default": "amazon-linux-2",
                    "enum": ["amazon-linux-2", "ubuntu-22.04", "windows-2022"],
                    "group": "Compute",
                    "isEssential": True,
                    "order": 12
                },
                "instance_count": {
                    "type": "number",
                    "title": "Instance Count",
                    "description": "Number of EC2 instances to launch",
                    "default": 1,
                    "minimum": 1,
                    "maximum": 10,
                    "group": "Compute",
                    "order": 13
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
                    "order": 20
                },
                "vpc_id": {
                    "type": "string",
                    "title": "Existing VPC ID",
                    "description": "ID of an existing VPC to deploy into",
                    "placeholder": "vpc-0abc123def456",
                    "visibleIf": {"vpc_mode": "existing"},
                    "group": "Networking",
                    "order": 21
                },
                "subnet_id": {
                    "type": "string",
                    "title": "Existing Subnet ID",
                    "description": "Subnet to launch the instance in",
                    "placeholder": "subnet-0abc123def456",
                    "visibleIf": {"vpc_mode": "existing"},
                    "group": "Networking",
                    "order": 22
                },
                "cidr_block": {
                    "type": "string",
                    "title": "VPC CIDR Block",
                    "description": "CIDR block for the new VPC (leave empty for auto-generated)",
                    "placeholder": "10.0.0.0/16",
                    "visibleIf": {"vpc_mode": "new"},
                    "group": "Networking",
                    "order": 23
                },
                # --- Security ---
                "enable_ssm": {
                    "type": "boolean",
                    "title": "Enable SSM Access",
                    "description": "Enable AWS Systems Manager for remote management (no SSH needed)",
                    "default": True,
                    "group": "Security",
                    "isEssential": True,
                    "order": 30
                },
                "enable_ssh_access": {
                    "type": "boolean",
                    "title": "Enable SSH Access",
                    "description": "Open port 22 for SSH connections",
                    "default": False,
                    "group": "Security",
                    "order": 31
                },
                "ssh_access_ip": {
                    "type": "string",
                    "title": "SSH Access IP",
                    "description": "IP address allowed for SSH (e.g. 203.0.113.0/32)",
                    "placeholder": "0.0.0.0/0",
                    "visibleIf": {"enable_ssh_access": True},
                    "group": "Security",
                    "order": 32
                },
                "key_name": {
                    "type": "string",
                    "title": "Key Pair Name",
                    "description": "EC2 key pair for SSH authentication",
                    "placeholder": "my-keypair",
                    "visibleIf": {"enable_ssh_access": True},
                    "group": "Security",
                    "order": 33
                },
                # --- Advanced ---
                "user_data": {
                    "type": "string",
                    "title": "User Data Script",
                    "description": "Custom startup script (overrides preset script)",
                    "format": "textarea",
                    "group": "Advanced",
                    "order": 40
                },
            },
            "required": ["project_name"]
        }
