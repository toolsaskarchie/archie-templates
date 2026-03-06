"""
AWS NAT Gateway Template
Creates a standalone AWS NAT Gateway using the NATGatewayComponent.
"""
from typing import Any, Dict, Optional
import pulumi
import pulumi_aws as aws

from provisioner.templates.base import template_registry, InfrastructureTemplate
from .config import NATGatewayAtomicConfig
from provisioner.utils.aws import get_standard_tags

@template_registry("aws-nat-gateway-atomic")
class NATGatewayAtomicTemplate(InfrastructureTemplate):
    """
    AWS NAT Gateway Template
    """
    
    def __init__(self, name: str = None, config: Dict[str, Any] = None, **kwargs):
        raw_config = config or kwargs or {}
        self.cfg = NATGatewayAtomicConfig(raw_config)
        
        if name is None:
            name = self.cfg.nat_name
            
        super().__init__(name, raw_config)
        self.nat: Optional[aws.ec2.NatGateway] = None

    def create_infrastructure(self) -> Dict[str, Any]:
        """Create NAT Gateway directly - shows as actual AWS resource in preview"""
        tags = get_standard_tags(
            project=self.cfg.project_name,
            environment=self.cfg.environment,
            template="nat-gateway-atomic"
        )
        # Use pattern: aws.ec2.NatGateway(f"{self.name}-natgateway", ...)
        self.nat = aws.ec2.NatGateway(
            self.name,
            subnet_id=self.cfg.subnet_id,
            allocation_id=self.cfg.allocation_id,
            tags={**tags, "Name": self.cfg.nat_name}
        )
        
        pulumi.export("nat_gateway_id", self.nat.id)
        
        return self.get_outputs()

    def get_outputs(self) -> Dict[str, Any]:
        if not self.nat:
            return {}
        return {
            "nat_gateway_id": self.nat.id,
            "public_ip": self.nat.public_ip
        }

    @classmethod
    def get_metadata(cls):
        return {
            "name": "nat-gateway-atomic",
            "title": "NAT Gateway",
            "description": "Standalone AWS NAT Gateway resource.",
            "category": "networking",
            "provider": "aws",
            "tier": "atomic"
        }
