"""
Configuration for ALB Atomic Template
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ALBAtomicConfig(BaseModel):
    """Configuration for ALB Atomic Template"""
    
    alb_name: Any = Field(..., description="Name of the Application Load Balancer")
    subnets: Any = Field(..., description="List of subnet IDs (minimum 2 required)")
    security_groups: Any = Field(..., description="List of security group IDs")
    internal: bool = Field(default=False, description="Whether the ALB is internal")
    enable_deletion_protection: bool = Field(default=False, description="Enable deletion protection")
    enable_http2: bool = Field(default=True, description="Enable HTTP/2")
    enable_cross_zone_load_balancing: bool = Field(default=True, description="Enable cross-zone load balancing")
    idle_timeout: int = Field(default=60, description="Idle timeout in seconds")
    project_name: str = Field(default="archie", description="Project name for tagging")
    environment: str = Field(default="dev", description="Environment (dev, staging, prod)")

    class Config:
        extra = "allow"
        arbitrary_types_allowed = True
