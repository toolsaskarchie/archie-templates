"""
Configuration for Aurora Non-Production Template
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AuroraNonProdConfig(BaseModel):
    """Configuration for Aurora Non-Production Cluster"""
    
    # Project identification
    project_name: Any = Field(..., description="Project name for resource naming and tagging")
    environment: Any = Field(default="nonprod", description="Environment (dev, test, staging, nonprod)")
    region: Any = Field(default="us-east-1", description="AWS region")
    
    # Database configuration
    db_name: Any = Field(default="mydb", description="Database name to create")
    db_username: Any = Field(default="postgres", description="Master username")
    
    # Engine configuration
    engine: str = Field(default="aurora-postgresql", description="Database engine (aurora-postgresql or aurora-mysql)")
    engine_version: str = Field(default="15", description="Engine version")
    
    # Instance configuration
    instance_class: str = Field(default="db.t3.medium", description="Instance class for cluster instances")
    instance_count: int = Field(default=1, description="Number of instances (1 primary + N-1 replicas)")
    
    # Networking
    vpc_mode: str = Field(default="new", description="VPC mode: 'new' or 'existing'")
    vpc_id: Any = Field(None, description="VPC ID (required if vpc_mode='existing')")
    subnet_ids: Any = Field(None, description="Subnet IDs for DB subnet group (2+ required)")
    vpc_cidr: Any = Field(default="10.0.0.0/16", description="VPC CIDR block (if creating new VPC)")
    use_random_vpc_cidr: Any = Field(default=True, description="Use random VPC CIDR to avoid conflicts")
    ssh_access_ip: Any = Field(None, description="Public IP for SSH/management access")
    allowed_cidr_blocks: Any = Field(None, description="CIDR blocks allowed to access database")
    db_security_group_id: Any = Field(None, description="Security group ID for database access")
    
    # Storage and backup
    backup_retention_days: int = Field(default=3, description="Automated backup retention period (days)")
    storage_encrypted: bool = Field(default=True, description="Enable storage encryption")
    deletion_protection_enabled: bool = Field(default=False, description="Enable deletion protection")
    skip_final_snapshot: bool = Field(default=True, description="Skip final snapshot on deletion (nonprod)")
    
    # Performance and monitoring
    enable_performance_insights: bool = Field(default=False, description="Enable Performance Insights")
    performance_insights_retention: int = Field(default=7, description="Performance Insights retention period (days)")
    
    # Multi-AZ
    multi_az: bool = Field(default=False, description="Deploy instances across multiple AZs")
    
    # Port
    port: Optional[int] = Field(None, description="Database port (5432 for PostgreSQL, 3306 for MySQL)")
    
    # Advanced options
    publicly_accessible: bool = Field(default=False, description="Make database publicly accessible")
    preferred_backup_window: Optional[str] = Field(None, description="Preferred backup window")
    preferred_maintenance_window: Optional[str] = Field(None, description="Preferred maintenance window")
    
    # Tagging
    tags: Dict[str, str] = Field(default_factory=dict, description="Additional tags")
    
    def __init__(self, config_dict: Dict[str, Any]):
        """Initialize from nested config dictionary"""
        # Handle both direct config and nested parameters structure
        if "parameters" in config_dict:
            aws_params = config_dict["parameters"].get("aws", config_dict["parameters"])
            # Merge top-level items into params if not present
            for key in ["project_name", "environment", "region", "projectName"]:
                if key in config_dict and key not in aws_params:
                    aws_params[key] = config_dict[key]
            aws_config = aws_params
        else:
            aws_config = config_dict
        
        # Mapping legacy keys
        if 'projectName' in aws_config and 'project_name' not in aws_config:
            aws_config['project_name'] = aws_config['projectName']
            
        super().__init__(**aws_config)
        
        # Handle SSH Access IP normalization
        if self.ssh_access_ip and '/' not in self.ssh_access_ip:
            self.ssh_access_ip = f"{self.ssh_access_ip}/32"
            
        # Initialize allowed_cidr_blocks
        if self.allowed_cidr_blocks is None:
            if self.ssh_access_ip:
                self.allowed_cidr_blocks = [self.ssh_access_ip]
            else:
                self.allowed_cidr_blocks = ["10.0.0.0/16"]
        elif isinstance(self.allowed_cidr_blocks, str):
            self.allowed_cidr_blocks = [self.allowed_cidr_blocks]
        
        # Set default port based on engine if not specified
        if self.port is None:
            if "mysql" in self.engine.lower():
                self.port = 3306
            else:  # PostgreSQL
                self.port = 5432
    
    @staticmethod
    def get_config_schema() -> Dict[str, Any]:
        """Get JSON schema for UI configuration."""
        from provisioner.templates.templates.aws.networking.vpc_nonprod.pulumi import VPCSimpleNonprodTemplate
        from provisioner.templates.shared.aws_schema import (
            get_database_selection_schema,
            get_security_connectivity_schema,
            get_observability_schema
        )
        
        # Pull base VPC Non-Prod schema
        vpc_schema = VPCSimpleNonprodTemplate.get_config_schema()
        
        # Merge logic: Aurora specific fields + VPC base
        properties = {
            # Shared essentials from VPC
            **vpc_schema.get("properties", {}),
        }
        
        # Aurora Specific additions
        properties.update({
            **get_database_selection_schema(engine="aurora-postgresql", order_offset=80),
            **get_security_connectivity_schema(include_rdp=False, order_offset=150),
            **get_observability_schema(order_offset=200),
        })
        
        # Required fields for Aurora Non-Prod
        required = list(set(vpc_schema.get("required", []) + ["db_name"]))
        
        return {
            "type": "object",
            "properties": properties,
            "required": required
        }

    class Config:
        extra = "allow"
        arbitrary_types_allowed = True
