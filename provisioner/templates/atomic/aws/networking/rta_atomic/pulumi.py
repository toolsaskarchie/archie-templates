"""
AWS Route Table Association Template
Creates a standalone AWS Route Table Association using the RouteTableAssociationComponent.
"""
from typing import Any, Dict, Optional
import pulumi
import pulumi_aws as aws

from provisioner.templates.base import template_registry, InfrastructureTemplate
from .config import RTAAtomicConfig

@template_registry("aws-rta-atomic")
class RouteTableAssociationAtomicTemplate(InfrastructureTemplate):
    """
    AWS Route Table Association Template
    """
    
    def __init__(self, name: str = None, config: Dict[str, Any] = None, **kwargs):
        raw_config = config or kwargs or {}
        self.cfg = RTAAtomicConfig(raw_config)
        
        if name is None:
            target = self.cfg.subnet_id or self.cfg.gateway_id
            name = f"rta-{target[-8:] if target else 'unknown'}"
            
        super().__init__(name, raw_config)
        self.rta: Optional[aws.ec2.RouteTableAssociation] = None

    def create_infrastructure(self) -> Dict[str, Any]:
        """Create Route Table Association directly - shows as actual AWS resource in preview"""
        # Use pattern: aws.ec2.RouteTableAssociation(f"{self.name}-routetableassociation", ...)
        self.rta = aws.ec2.RouteTableAssociation(
            self.name,
            route_table_id=self.cfg.route_table_id,
            subnet_id=self.cfg.subnet_id,
            gateway_id=self.cfg.gateway_id
        )
        
        return self.get_outputs()

    def get_outputs(self) -> Dict[str, Any]:
        if not self.rta:
            return {}
        return {
            "rta_id": self.rta.id
        }

    @classmethod
    def get_metadata(cls):
        return {
            "name": "rta-atomic",
            "title": "Route Table Association",
            "description": "Standalone AWS Route Table Association resource.",
            "category": "networking",
            "provider": "aws",
            "tier": "atomic"
        }
