"""
AWS NACL Template
Creates a standalone AWS Network ACL using the NACLComponent.
"""
from typing import Any, Dict, Optional
import pulumi
import pulumi_aws as aws

from provisioner.templates.base import template_registry, InfrastructureTemplate
from .config import NACLAtomicConfig
from provisioner.utils.aws import get_standard_tags

@template_registry("aws-nacl-atomic")
class NACLAtomicTemplate(InfrastructureTemplate):
    """
    AWS NACL Template
    """
    
    def __init__(self, name: str = None, config: Dict[str, Any] = None, **kwargs):
        raw_config = config or kwargs or {}
        self.cfg = NACLAtomicConfig(raw_config)
        
        if name is None:
            name = self.cfg.nacl_name
            
        super().__init__(name, raw_config)
        self.nacl: Optional[aws.ec2.NetworkAcl] = None

    def create_infrastructure(self) -> Dict[str, Any]:
        """Create NACL directly - shows as actual AWS resource in preview"""
        tags = get_standard_tags(
            project=self.cfg.project_name,
            environment=self.cfg.environment,
            template="nacl-atomic"
        )
        # Use pattern: aws.ec2.NetworkAcl(f"{self.name}-networkacl", ...)
        self.nacl = aws.ec2.NetworkAcl(
            self.name,
            vpc_id=self.cfg.vpc_id,
            subnet_ids=self.cfg.subnet_ids,
            ingress=self.cfg.ingress,
            egress=self.cfg.egress,
            tags={**tags, "Name": self.cfg.nacl_name}
        )
        
        pulumi.export("nacl_id", self.nacl.id)
        
        return self.get_outputs()

    def get_outputs(self) -> Dict[str, Any]:
        if not self.nacl:
            return {}
        return {
            "nacl_id": self.nacl.id
        }

    @classmethod
    def get_metadata(cls):
        return {
            "name": "nacl-atomic",
            "title": "NACL",
            "description": "Standalone AWS Network ACL resource.",
            "category": "networking",
            "provider": "aws",
            "tier": "atomic"
        }
