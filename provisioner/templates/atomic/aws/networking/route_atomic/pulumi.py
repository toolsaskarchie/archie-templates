"""
AWS Route Template
Creates a standalone AWS Route using the RouteComponent.
"""
from typing import Any, Dict, Optional
import pulumi
import pulumi_aws as aws

from provisioner.templates.base import template_registry, InfrastructureTemplate
from .config import RouteAtomicConfig

@template_registry("aws-route-atomic")
class RouteAtomicTemplate(InfrastructureTemplate):
    """
    AWS Route Template
    """
    
    def __init__(self, name: str = None, config: Dict[str, Any] = None, **kwargs):
        raw_config = config or kwargs or {}
        self.cfg = RouteAtomicConfig(raw_config)
        
        if name is None:
            name = f"route-{self.cfg.destination_cidr_block.replace('/', '-')}"
            
        super().__init__(name, raw_config)
        self.route: Optional[aws.ec2.Route] = None

    def create_infrastructure(self) -> Dict[str, Any]:
        """Create Route directly - shows as actual AWS resource in preview"""
        # Use pattern: aws.ec2.Route(f"{self.name}-route", ...)
        self.route = aws.ec2.Route(
            self.name,
            route_table_id=self.cfg.route_table_id,
            destination_cidr_block=self.cfg.destination_cidr_block,
            gateway_id=self.cfg.gateway_id,
            nat_gateway_id=self.cfg.nat_gateway_id,
            vpc_peering_connection_id=self.cfg.vpc_peering_connection_id
        )
        
        return self.get_outputs()

    def get_outputs(self) -> Dict[str, Any]:
        if not self.route:
            return {}
        return {
            "route_id": self.route.id
        }

    @classmethod
    def get_metadata(cls):
        return {
            "name": "route-atomic",
            "title": "Route",
            "description": "Standalone AWS Route resource.",
            "category": "networking",
            "provider": "aws",
            "tier": "atomic"
        }
