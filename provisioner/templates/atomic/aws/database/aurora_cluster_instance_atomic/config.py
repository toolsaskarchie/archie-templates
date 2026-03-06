"""
Configuration for Aurora Cluster Instance Atomic Template
"""
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class AuroraClusterInstanceAtomicConfig(BaseModel):
    """Configuration for Aurora Cluster Instance"""
    
    # Required fields
    identifier: Any = Field(..., description="Instance identifier")
    cluster_identifier: Any = Field(..., description="Aurora cluster identifier this instance belongs to")
    instance_class: Any = Field(..., description="Instance class (e.g., db.t3.medium, db.r5.large)")
    engine: Any = Field(..., description="Database engine (aurora-postgresql or aurora-mysql)")
    
    # Optional fields
    engine_version: Optional[str] = Field(None, description="Database engine version")
    publicly_accessible: bool = Field(default=False, description="Make instance publicly accessible")
    availability_zone: Optional[str] = Field(None, description="Availability zone for the instance")
    
    # Performance and monitoring
    performance_insights_enabled: bool = Field(default=False, description="Enable Performance Insights")
    performance_insights_retention_period: Optional[int] = Field(None, description="Performance Insights retention period")
    monitoring_interval: int = Field(default=0, description="Enhanced monitoring interval in seconds (0, 1, 5, 10, 15, 30, 60)")
    monitoring_role_arn: Optional[str] = Field(None, description="IAM role ARN for enhanced monitoring")
    
    # Maintenance
    preferred_maintenance_window: Optional[str] = Field(None, description="Preferred maintenance window")
    auto_minor_version_upgrade: bool = Field(default=True, description="Enable automatic minor version upgrades")
    apply_immediately: bool = Field(default=False, description="Apply changes immediately")
    
    # Tagging
    project_name: str = Field(..., description="Project name for tagging")
    environment: str = Field(..., description="Environment name")
    region: Optional[str] = Field(None, description="AWS region")
    
    # Extra arguments
    extra_args: Dict[str, Any] = Field(default_factory=dict, description="Additional arguments for instance")
    
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
