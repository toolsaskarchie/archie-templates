"""
AWS EIP Template
Creates a standalone AWS Elastic IP using the EIPComponent.
"""
from typing import Any, Dict, Optional
import pulumi
import pulumi_aws as aws

from provisioner.templates.base import template_registry, InfrastructureTemplate
from .config import EIPAtomicConfig
from provisioner.utils.aws import get_standard_tags

@template_registry("aws-eip-atomic")
class EIPAtomicTemplate(InfrastructureTemplate):
    """
    AWS EIP Template
    """
    
    def __init__(self, name: str = None, config: Dict[str, Any] = None, **kwargs):
        raw_config = config or kwargs or {}
        self.cfg = EIPAtomicConfig(raw_config)
        
        if name is None:
            name = self.cfg.eip_name
            
        super().__init__(name, raw_config)
        self.eip: Optional[aws.ec2.Eip] = None

    def create_infrastructure(self) -> Dict[str, Any]:
        """Create EIP directly - shows as actual AWS resource in preview"""
        tags = get_standard_tags(
            project=self.cfg.project_name,
            environment=self.cfg.environment,
            template="eip-atomic"
        )
        # Use pattern: aws.ec2.Eip(f"{self.name}-eip", ...)
        self.eip = aws.ec2.Eip(
            self.name,
            tags={**tags, "Name": self.cfg.eip_name}
        )
        
        pulumi.export("eip_id", self.eip.id)
        pulumi.export("public_ip", self.eip.public_ip)
        
        return self.get_outputs()

    def get_outputs(self) -> Dict[str, Any]:
        if not self.eip:
            return {}
        return {
            "eip_id": self.eip.id,
            "public_ip": self.eip.public_ip
        }

    @classmethod
    def get_metadata(cls):
        return {
            "name": "eip-atomic",
            "title": "Elastic IP",
            "description": "Standalone AWS Elastic IP resource.",
            "category": "networking",
            "provider": "aws",
            "tier": "atomic"
        }
