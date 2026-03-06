"""
Configuration for Aurora Cluster Atomic Template
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AuroraClusterAtomicConfig(BaseModel):
    """Configuration for Aurora Cluster"""
    
    # Required fields
    cluster_identifier: Any = Field(..., description="Aurora cluster identifier")
    engine: Any = Field(default="aurora-postgresql", description="Database engine (aurora-postgresql or aurora-mysql)")
    master_username: Any = Field(..., description="Master username for the cluster")
    master_password: Any = Field(..., description="Master password for the cluster")
    
    # Networking
    db_subnet_group_name: Any = Field(None, description="DB subnet group name")
    vpc_security_group_ids: Any = Field(default_factory=list, description="VPC security group IDs")
    
    # Engine configuration
    engine_version: Optional[str] = Field(None, description="Database engine version")
    engine_mode: str = Field(default="provisioned", description="Engine mode (provisioned or serverless)")
    
    # Backup and maintenance
    backup_retention_period: int = Field(default=7, description="Number of days to retain backups")
    preferred_backup_window: Optional[str] = Field(None, description="Preferred backup window (e.g., 03:00-04:00)")
    preferred_maintenance_window: Optional[str] = Field(None, description="Preferred maintenance window")
    
    # Storage and encryption
    storage_encrypted: bool = Field(default=True, description="Enable storage encryption")
    kms_key_id: Optional[str] = Field(None, description="KMS key ID for encryption")
    
    # Availability
    availability_zones: Optional[List[str]] = Field(None, description="Availability zones for the cluster")
    
    # Database configuration
    database_name: Optional[str] = Field(None, description="Name of the database to create")
    port: Optional[int] = Field(None, description="Database port (5432 for PostgreSQL, 3306 for MySQL)")
    
    # Advanced options
    deletion_protection: bool = Field(default=False, description="Enable deletion protection")
    skip_final_snapshot: bool = Field(default=True, description="Skip final snapshot on deletion")
    final_snapshot_identifier: Optional[str] = Field(None, description="Final snapshot identifier")
    apply_immediately: bool = Field(default=False, description="Apply changes immediately")
    enabled_cloudwatch_logs_exports: Optional[List[str]] = Field(None, description="CloudWatch log types to export")
    
    # Tagging
    project_name: str = Field(..., description="Project name for tagging")
    environment: str = Field(..., description="Environment name")
    region: Optional[str] = Field(None, description="AWS region")
    
    # Extra arguments
    extra_args: Dict[str, Any] = Field(default_factory=dict, description="Additional arguments for cluster")
    
    def __init__(self, config_dict: Dict[str, Any]):
        """Initialize from nested config dictionary"""
        if "parameters" in config_dict and "aws" in config_dict["parameters"]:
            aws_config = config_dict["parameters"]["aws"]
        else:
            aws_config = config_dict
        
        super().__init__(**aws_config)
    
    class Config:
        extra = "allow"
        arbitrary_types_allowed = True
