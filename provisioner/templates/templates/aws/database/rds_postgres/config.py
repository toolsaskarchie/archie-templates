"""
Configuration parser for RDS PostgreSQL Production Template
"""
from typing import Dict, Any, Optional

class RDSPostgresConfig:
    """Configuration for RDS PostgreSQL database"""
    
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
        self.environment = self.raw_config.get('environment', 'prod')
        self.region = self.raw_config.get('region', 'us-east-1')
        self.tags = self.raw_config.get('tags', {})

        # Database Settings
        self.db_name = self.get_parameter('dbName', self.get_parameter('db_name', 'mydb'))
        self.db_username = self.get_parameter('dbUsername', self.get_parameter('db_username', 'admin'))
        self.db_instance_class = self.get_parameter('instanceClass', self.get_parameter('instance_class', 'db.t3.medium'))
        self.allocated_storage = int(self.get_parameter('allocatedStorage', self.get_parameter('allocated_storage', 100)))
        self.max_allocated_storage = self.get_parameter('maxAllocatedStorage', self.get_parameter('max_allocated_storage'))
        if self.max_allocated_storage:
            self.max_allocated_storage = int(self.max_allocated_storage)
            
        self.engine_version = self.get_parameter('engineVersion', self.get_parameter('engine_version', '15'))
        self.backup_retention_days = int(self.get_parameter('backupRetentionDays', self.get_parameter('backup_retention_days', 30)))
        
        # High Availability & Cost
        self.multi_az = self.get_parameter('multiAz', self.get_parameter('multi_az', True))
        self.storage_encrypted = self.get_parameter('storageEncrypted', self.get_parameter('storage_encrypted', True))
        self.skip_final_snapshot = self.get_parameter('skipFinalSnapshot', self.get_parameter('skip_final_snapshot', False))
        
        # Networking & Connectivity
        self.vpc_mode = self.get_parameter('vpc_mode', self.get_parameter('vpcMode', 'new'))
        self.vpc_id = self.get_parameter('vpc_id', self.get_parameter('vpcId'))
        self.subnet_ids = self.get_parameter('subnet_ids', self.get_parameter('subnetIds', []))
        self.vpc_cidr = self.get_parameter('vpc_cidr', self.get_parameter('vpcCidr', '10.0.0.0/16'))
        self.use_random_vpc_cidr = self.get_parameter('use_random_vpc_cidr', self.get_parameter('useRandomVpcCidr', True))
        
        self.ssh_access_ip = self.get_parameter('ssh_access_ip', self.get_parameter('sshAccessIp'))
        if self.ssh_access_ip and '/' not in self.ssh_access_ip:
            self.ssh_access_ip = f"{self.ssh_access_ip}/32"

        self.allowed_cidr_blocks = self.get_parameter('allowed_cidr_blocks', self.get_parameter('allowedCidrBlocks'))
        if not self.allowed_cidr_blocks:
            self.allowed_cidr_blocks = [self.ssh_access_ip] if self.ssh_access_ip else ['10.0.0.0/16']
        elif isinstance(self.allowed_cidr_blocks, str):
            self.allowed_cidr_blocks = [self.allowed_cidr_blocks]

        self._validate()

    @property
    def project_name(self) -> str:
        """Get project name from config."""
        return (
            self.get_parameter('projectName') or
            self.get_parameter('project_name') or
            self.raw_config.get('projectName') or
            self.raw_config.get('project_name') or
            'archie-db-prod'
        )

    def get_parameter(self, key: str, default: Any = None) -> Any:
        """Get a parameter from the configuration."""
        if self.template:
            return self.template.get_parameter(key, default)
        return self.parameters.get(key, default)
    
    def _validate(self):
        """Validate configuration"""
        if not self.db_name:
            raise ValueError("dbName is required")
        if not self.db_username:
            raise ValueError("dbUsername is required")
        
        # Validate DB name format
        if not self.db_name[0].isalpha():
            raise ValueError("dbName must start with a letter")
        if not self.db_name.replace('_', '').isalnum():
            raise ValueError("dbName must be alphanumeric with underscores")
        
        # Validate storage
        if self.allocated_storage < 20:
            raise ValueError("allocatedStorage must be at least 20 GB")
        
        if self.environment != 'prod' and self.environment != 'production':
            # This is a warning/log only in some cases, but here we expect prod
            pass

    @staticmethod
    def get_config_schema() -> Dict[str, Any]:
        """Get JSON schema for UI configuration."""
        from provisioner.templates.templates.aws.networking.vpc_prod.pulumi import VPCProdTemplate
        from provisioner.templates.shared.aws_schema import (
            get_database_selection_schema,
            get_security_connectivity_schema
        )
        
        # Pull base VPC Prod schema
        vpc_schema = VPCProdTemplate.get_config_schema()
        
        # Merge logic: RDS specific fields + VPC base
        properties = {
            # Shared essentials from VPC
            **vpc_schema.get("properties", {}),
        }
        
        # RDS Specific additions
        properties.update({
            **get_database_selection_schema(engine="postgres", order_offset=80),
            **get_security_connectivity_schema(include_rdp=False, order_offset=150),
        })
        
        # Required fields for RDS Prod
        required = list(set(vpc_schema.get("required", []) + ["dbName", "dbUsername"]))

        # Add team_name to Tags group
        properties["team_name"] = {
            "type": "string",
            "default": "",
            "title": "Team Name",
            "description": "Team that owns this resource",
            "order": 250,
            "group": "Tags",
        }

        return {
            "type": "object",
            "properties": properties,
            "required": required
        }
