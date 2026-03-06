"""
AWS Internet Gateway Template
Creates a standalone AWS Internet Gateway using the InternetGatewayComponent.
"""
from typing import Any, Dict, Optional
import pulumi
import pulumi_aws as aws

from provisioner.templates.base import template_registry, InfrastructureTemplate
from .config import IGWAtomicConfig
from provisioner.utils.aws import get_standard_tags

@template_registry("aws-igw-atomic")
class IGWAtomicTemplate(InfrastructureTemplate):
    """
    AWS Internet Gateway Template
    """
    
    def __init__(self, name: str = None, config: Dict[str, Any] = None, **kwargs):
        raw_config = config or kwargs or {}
        self.cfg = IGWAtomicConfig(raw_config)
        
        if name is None:
            name = self.cfg.igw_name
            
        super().__init__(name, raw_config)
        self.igw: Optional[aws.ec2.InternetGateway] = None

    def create_infrastructure(self) -> Dict[str, Any]:
        """Create IGW directly - shows as actual AWS resource in preview"""
        tags = get_standard_tags(
            project=self.cfg.project_name,
            environment=self.cfg.environment,
            template="igw-atomic"
        )
        # Use pattern: aws.ec2.InternetGateway(f"{self.name}-internetgateway", ...)
        self.igw = aws.ec2.InternetGateway(
            self.name,  # Use self.name directly
            vpc_id=self.cfg.vpc_id,
            tags={**tags, "Name": self.cfg.igw_name}
        )
        
        pulumi.export("igw_id", self.igw.id)
        pulumi.export("igw_arn", self.igw.arn)
        
        return self.get_outputs()

    def get_outputs(self) -> Dict[str, Any]:
        if not self.igw:
            return {}
        return {
            "igw_id": self.igw.id,
            "igw_arn": self.igw.arn
        }

    @classmethod
    def get_metadata(cls):
        return {
            "name": "igw-atomic",
            "title": "Internet Gateway",
            "description": "Standalone AWS Internet Gateway resource.",
            "category": "networking",
            "provider": "aws",
            "tier": "atomic"
        }
