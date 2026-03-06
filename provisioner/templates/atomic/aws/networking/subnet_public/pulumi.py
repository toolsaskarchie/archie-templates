"""
Public Subnet Template

Creates a public subnet in an existing VPC with optional Internet Gateway and route table.
This is an atomic component for building custom VPC architectures.
"""

from typing import Any, Dict, Optional
import pulumi
import pulumi_aws as aws

from provisioner.templates.base import (
    InfrastructureTemplate,
    template_registry
)
from provisioner.utils.aws import get_standard_tags
from provisioner.templates.atomic.aws.networking.subnet_public.config import PublicSubnetConfig

@template_registry("aws-subnet-public")
class PublicSubnetTemplate(InfrastructureTemplate):
    """
    Public Subnet Component
    Creates a public subnet in an existing VPC
    """
    @classmethod
    def get_metadata(cls):
        from provisioner.templates.base.template import TemplateMetadata, TemplateCategory
        return TemplateMetadata(
            name="aws-subnet-public",
            description="Atomic component that creates a public subnet in an existing VPC with automatic tag management.",
            category=TemplateCategory.NETWORKING,
            version="1.0.0",
            author="InnovativeApps",
            tags=["aws", "vpc", "subnet", "networking"],
            estimated_cost="$0",
            complexity="low",
            deployment_time="< 1m",
            is_listed_in_marketplace=False,
            title="AWS Public Subnet"
        )
    def __init__(self, name: str = None, config: Dict[str, Any] = None, aws: Dict[str, Any] = None, **kwargs):
        raw_config = config or aws or kwargs or {}
        if name is None:
            name = raw_config.get('subnetName') or raw_config.get('subnet_name', 'public-subnet')
        super().__init__(name, raw_config)
        self.cfg = PublicSubnetConfig(raw_config)
        self.subnet: Optional[aws.ec2.Subnet] = None

    def create_infrastructure(self) -> Dict[str, Any]:
        """Create public subnet infrastructure directly - shows as actual AWS resource in preview"""
        vpc_id = self.cfg.vpc_id
        cidr_block = self.cfg.cidr_block
        availability_zone= self.cfg.availability_zone
        
        tags = get_standard_tags(
            project=self.cfg.project_name,
            environment=self.cfg.environment,
            template="public-subnet"
        )
        
        # Create public subnet using Component
        # Use pattern: aws.ec2.Subnet(f"{self.name}-subnet", ...)
        self.subnet = aws.ec2.Subnet(
            self.name,
            vpc_id=vpc_id,
            cidr_block=cidr_block,
            availability_zone=az,
            public=True,
            tags={**tags, "Name": f"{self.name}-public", "Type": "Public"}
        )
        
        return {
            "subnet_id": self.subnet.id,
            "subnet_cidr": self.subnet.cidr_block,
            "subnet_az": self.subnet.availability_zone
        }
