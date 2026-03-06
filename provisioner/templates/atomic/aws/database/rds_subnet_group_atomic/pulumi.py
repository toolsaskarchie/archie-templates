"""
AWS RDS Subnet Group Template
Creates a standalone AWS RDS Subnet Group directly (no ComponentResource wrapper).
"""
from typing import Any, Dict, Optional
import pulumi
import pulumi_aws as aws

from provisioner.templates.base import template_registry, InfrastructureTemplate
from .config import RDSSubnetGroupAtomicConfig
from provisioner.utils.aws import get_standard_tags

@template_registry("aws-rds-subnet-group-atomic")
class RDSSubnetGroupAtomicTemplate(InfrastructureTemplate):
    """
    AWS RDS Subnet Group Template
    """
    
    def __init__(self, name: str = None, config: Dict[str, Any] = None, **kwargs):
        raw_config = config or kwargs or {}
        self.cfg = RDSSubnetGroupAtomicConfig(raw_config)
        
        if name is None:
            name = self.cfg.subnet_group_name
            
        super().__init__(name, raw_config)
        self.subnet_group: Optional[aws.rds.SubnetGroup] = None

    def create_infrastructure(self) -> Dict[str, Any]:
        """Create RDS Subnet Group directly - shows as actual AWS resource in preview"""
        tags = get_standard_tags(
            project=self.cfg.project_name,
            environment=self.cfg.environment,
            template="rds-subnet-group-atomic"
        )
        
        self.subnet_group = aws.rds.SubnetGroup(
            f"{self.name}-subnet-group",
            name=self.cfg.subnet_group_name,
            subnet_ids=self.cfg.subnet_ids,
            description=self.cfg.description,
            tags={**tags, "Name": self.cfg.subnet_group_name}
        )
        
        pulumi.export("rds_subnet_group_name", self.subnet_group.name)
        
        return self.get_outputs()

    def get_outputs(self) -> Dict[str, Any]:
        if not self.subnet_group:
            return {}
        return {
            "subnet_group_name": self.subnet_group.name,
            "subnet_group_id": self.subnet_group.id
        }

    @classmethod
    def get_metadata(cls) -> 'TemplateMetadata':
        from provisioner.templates.base.template import TemplateMetadata, TemplateCategory
        return TemplateMetadata(
            name="aws-rds-subnet-group-atomic",
            title="RDS Subnet Group",
            description="Standalone AWS RDS Subnet Group resource.",
            category=TemplateCategory.DATABASE,
            author="InnovativeApps",
            version="1.0.0",
            tags=["aws", "database", "rds", "atomic"],
            estimated_cost="N/A",
            complexity="low",
            deployment_time="2-4 minutes"
        )
