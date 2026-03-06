"""
Configuration for EKS Atomic Template
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class EKSAtomicConfig(BaseModel):
    """Configuration for EKS Atomic Template"""
    
    cluster_name: Any = Field(..., description="Name of the EKS cluster")
    role_arn: Any = Field(..., description="IAM role ARN for the EKS cluster")
    subnet_ids: Any = Field(..., description="List of subnet IDs (minimum 2 required)")
    security_group_ids: Any = Field(default=None, description="List of security group IDs")
    endpoint_private_access: bool = Field(default=True, description="Enable private API server endpoint")
    endpoint_public_access: bool = Field(default=True, description="Enable public API server endpoint")
    public_access_cidrs: List[str] = Field(default=["0.0.0.0/0"], description="CIDR blocks for public access")
    version: str = Field(default="1.28", description="Kubernetes version")
    enabled_cluster_log_types: List[str] = Field(
        default=["api", "audit", "authenticator", "controllerManager", "scheduler"],
        description="Enabled cluster log types"
    )
    project_name: str = Field(default="archie", description="Project name for tagging")
    environment: str = Field(default="dev", description="Environment (dev, staging, prod)")

    class Config:
        extra = "allow"
        arbitrary_types_allowed = True
