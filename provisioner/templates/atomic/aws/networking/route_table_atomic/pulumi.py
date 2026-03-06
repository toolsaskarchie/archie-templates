"""
AWS Route Table Template
Creates a standalone AWS Route Table using the RouteTableComponent.
"""
from typing import Any, Dict, Optional
import pulumi
import pulumi_aws as aws

from provisioner.templates.base import template_registry, InfrastructureTemplate
from .config import RouteTableAtomicConfig
from provisioner.utils.aws import get_standard_tags

@template_registry("aws-route-table-atomic")
class RouteTableAtomicTemplate(InfrastructureTemplate):
    """
    AWS Route Table Template
    """
    
    def __init__(self, name: str = None, config: Dict[str, Any] = None, **kwargs):
        raw_config = config or kwargs or {}
        self.cfg = RouteTableAtomicConfig(raw_config)
        
        if name is None:
            name = self.cfg.route_table_name
            
        super().__init__(name, raw_config)
        self.route_table: Optional[aws.ec2.RouteTable] = None

    def create_infrastructure(self) -> Dict[str, Any]:
        """Create Route Table directly - shows as actual AWS resource in preview"""
        tags = get_standard_tags(
            project=self.cfg.project_name,
            environment=self.cfg.environment,
            template="route-table-atomic"
        )
        # Use pattern: aws.ec2.RouteTable(f"{self.name}-routetable", ...)
        self.route_table = aws.ec2.RouteTable(
            self.name,
            vpc_id=self.cfg.vpc_id,
            tags={**tags, "Name": self.cfg.route_table_name}
        )
        
        pulumi.export("route_table_id", self.route_table.id)
        
        return self.get_outputs()

    def get_outputs(self) -> Dict[str, Any]:
        if not self.route_table:
            return {}
        return {
            "route_table_id": self.route_table.id
        }

    @classmethod
    def get_metadata(cls):
        return {
            "name": "route-table-atomic",
            "title": "Route Table",
            "description": "Standalone AWS Route Table resource.",
            "category": "networking",
            "provider": "aws",
            "tier": "atomic"
        }
