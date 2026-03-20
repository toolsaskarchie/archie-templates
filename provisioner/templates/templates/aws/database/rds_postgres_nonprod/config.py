"""
Configuration for RDS PostgreSQL Non-Production Template

Optimized for development, testing, and staging environments with:
- Cost-optimized defaults (db.t3.micro, 20GB storage)
- Shorter backup retention (3 days)
- Single-AZ deployment
- Automated start/stop scheduling support
"""
from typing import Dict, Any, List, Optional


class RDSPostgresNonProdConfig:
    """Configuration for RDS PostgreSQL Non-Production template"""

    def __init__(self, raw_config: Dict[str, Any]):
        """
        Initialize configuration from deployment payload

        Args:
            raw_config: Raw configuration from UI/API containing:
                - parameters: AWS-specific settings
                - credentials: AWS credentials
                - environment: Deployment environment (nonprod)
                - region: AWS region
        """
        self.raw_config = raw_config

        # Extract AWS-specific parameters
        self.parameters = self.raw_config.get('parameters', {}).get('aws', {}) or self.raw_config.get('parameters', {})

        # Core deployment attributes
        self.environment = self.raw_config.get('environment', 'nonprod')
        self.region = self.raw_config.get('region', 'us-east-1')

        # Project identification
        self.project_name = (
            self.raw_config.get('projectName') or
            self.parameters.get('projectName') or
            'my-project'
        )

        # Database configuration
        self.db_name = (
            self.raw_config.get('dbName') or
            self.parameters.get('dbName') or
            'mydb'
        )
        self.db_username = (
            self.raw_config.get('dbUsername') or
            self.parameters.get('dbUsername') or
            'postgres'
        )

        # Instance configuration - nonprod defaults
        self.db_instance_class = self.get_parameter('instanceClass', 'db.t3.micro')
        self.allocated_storage = int(self.get_parameter('allocatedStorage', 20))
        self.max_allocated_storage = int(self.get_parameter('maxAllocatedStorage', 100))
        self.engine_version = self.get_parameter('engineVersion', '15')

        # High availability - disabled for nonprod by default
        self.multi_az = self.get_parameter('multiAz', False)

        # Backup configuration - reduced for nonprod
        self.backup_retention_days = int(self.get_parameter('backupRetentionDays', 3))
        self.skip_final_snapshot = self.get_parameter('skipFinalSnapshot', True)

        # Security configuration
        self.storage_encrypted = self.get_parameter('storageEncrypted', True)
        self.publicly_accessible = self.get_parameter('publiclyAccessible', False)

        # Network configuration
        self.vpc_mode = self.raw_config.get('vpcMode') or self.parameters.get('vpcMode', 'new')
        self.vpc_id = self.raw_config.get('vpcId') or self.parameters.get('vpcId')
        self.subnet_ids = self.raw_config.get('subnetIds') or self.parameters.get('subnetIds', [])
        self.ssh_access_ip = self.raw_config.get('ssh_access_ip') or self.parameters.get('ssh_access_ip')
        if self.ssh_access_ip and '/' not in self.ssh_access_ip:
            self.ssh_access_ip = f"{self.ssh_access_ip}/32"
            
        self.allowed_cidr_blocks = (
            self.raw_config.get('allowedCidrBlocks') or
            self.parameters.get('allowedCidrBlocks') or
            ([self.ssh_access_ip] if self.ssh_access_ip else ['10.0.0.0/16'])
        )
        self.vpc_cidr = self.raw_config.get('vpcCidr') or self.parameters.get('vpcCidr', '10.0.0.0/16')
        self.use_random_vpc_cidr = self.raw_config.get('useRandomVpcCidr') or self.parameters.get('useRandomVpcCidr', True)

        # Cost optimization features
        self.enable_auto_stop = self.get_parameter('enableAutoStop', False)
        self.auto_stop_schedule = self.get_parameter('autoStopSchedule', 'cron(0 22 * * ? *)')  # 10 PM UTC
        self.auto_start_schedule = self.get_parameter('autoStartSchedule', 'cron(0 6 * * MON-FRI *)')  # 6 AM UTC weekdays

        # Monitoring configuration
        self.enable_performance_insights = self.get_parameter('enablePerformanceInsights', False)
        self.performance_insights_retention = int(self.get_parameter('performanceInsightsRetention', 7))

        # Tags
        self.tags = self.raw_config.get('tags', {})

        # Validate configuration
        self._validate()

    def _validate(self):
        """Validate required configuration fields"""
        if not self.db_name:
            raise ValueError("dbName is required")
        if not self.db_username:
            raise ValueError("dbUsername is required")
        if not self.project_name:
            raise ValueError("projectName is required")

        # Validate DB name format (PostgreSQL naming rules)
        if not self.db_name[0].isalpha():
            raise ValueError("dbName must start with a letter")
        if not self.db_name.replace('_', '').isalnum():
            raise ValueError("dbName must be alphanumeric with underscores only")
        if len(self.db_name) > 63:
            raise ValueError("dbName must be 63 characters or less")

        # Validate username
        if len(self.db_username) > 63:
            raise ValueError("dbUsername must be 63 characters or less")

        # Validate storage limits
        if self.allocated_storage < 20:
            raise ValueError("allocatedStorage must be at least 20 GB")
        if self.allocated_storage > 65536:
            raise ValueError("allocatedStorage must be 65536 GB or less")
        if self.max_allocated_storage < self.allocated_storage:
            raise ValueError("maxAllocatedStorage must be greater than or equal to allocatedStorage")

        # Validate instance class for nonprod
        valid_nonprod_classes = [
            'db.t3.micro', 'db.t3.small', 'db.t3.medium', 'db.t3.large',
            'db.t4g.micro', 'db.t4g.small', 'db.t4g.medium',
            'db.m5.large', 'db.m5.xlarge'
        ]
        if self.db_instance_class not in valid_nonprod_classes:
            raise ValueError(f"instanceClass must be one of {valid_nonprod_classes} for nonprod")

        # Validate backup retention
        if self.backup_retention_days < 0 or self.backup_retention_days > 35:
            raise ValueError("backupRetentionDays must be between 0 and 35")

        # Validate subnet requirements
        if self.subnet_ids and len(self.subnet_ids) < 2:
            raise ValueError("At least 2 subnets in different AZs are required for RDS")

        # Ensure nonprod environment
        if self.environment not in ['dev', 'test', 'staging', 'nonprod', 'development']:
            raise ValueError(f"This template is for nonprod environments only. Got: {self.environment}")
        
        # Validate VPC configuration
        if self.vpc_mode == 'existing' and not self.vpc_id:
            raise ValueError("vpc_id is required when vpc_mode='existing'. Either provide a vpc_id or set vpc_mode='new' to create a new VPC.")

    def get_parameter(self, key: str, default: Any = None) -> Any:
        """
        Get a parameter from AWS-specific configuration

        Args:
            key: Parameter name
            default: Default value if not found

        Returns:
            Parameter value or default
        """
        return self.parameters.get(key, default)

    @property
    def resource_prefix(self) -> str:
        """Get resource name prefix"""
        return f"archie-{self.project_name}-{self.environment}"

    @property
    def deletion_protection_enabled(self) -> bool:
        """Deletion protection disabled for nonprod"""
        return False
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
                # --- Database ---
                "db_name": {
                    "type": "string",
                    "title": "Database Name",
                    "description": "Name of the PostgreSQL database to create",
                    "default": "mydb",
                    "group": "Database",
                    "isEssential": True,
                    "order": 10
                },
                "db_username": {
                    "type": "string",
                    "title": "Master Username",
                    "description": "Master username for the database",
                    "default": "postgres",
                    "group": "Database",
                    "isEssential": True,
                    "order": 11
                },
                "engine_version": {
                    "type": "string",
                    "title": "PostgreSQL Version",
                    "description": "PostgreSQL engine version",
                    "default": "15",
                    "enum": ["13", "14", "15", "16"],
                    "group": "Database",
                    "isEssential": True,
                    "order": 12
                },
                "instance_class": {
                    "type": "string",
                    "title": "Instance Class",
                    "description": "RDS instance size",
                    "default": "db.t3.micro",
                    "enum": ["db.t3.micro", "db.t3.small", "db.t3.medium", "db.t3.large", "db.t4g.micro", "db.t4g.small", "db.m5.large"],
                    "group": "Database",
                    "isEssential": True,
                    "order": 13
                },
                "allocated_storage": {
                    "type": "number",
                    "title": "Storage (GB)",
                    "description": "Initial allocated storage in gigabytes",
                    "default": 20,
                    "minimum": 20,
                    "maximum": 1000,
                    "group": "Database",
                    "order": 14
                },
                "backup_retention": {
                    "type": "number",
                    "title": "Backup Retention (days)",
                    "description": "Number of days to retain automated backups",
                    "default": 7,
                    "minimum": 0,
                    "maximum": 35,
                    "group": "Database",
                    "order": 15
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
                # --- Security ---
                "deletion_protection": {
                    "type": "boolean",
                    "title": "Deletion Protection",
                    "description": "Prevent accidental deletion of the database",
                    "default": False,
                    "group": "Security",
                    "order": 30
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
                "ssh_access_ip": {
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
            },
            "required": ["project_name", "db_name"]
        }
