"""
AWS VPC Endpoint Template
Creates a standalone AWS VPC Endpoint using the VPCEndpointComponent.
"""
from typing import Any, Dict, Optional
import pulumi
import pulumi_aws as aws

from provisioner.templates.base import template_registry, InfrastructureTemplate
from .config import VPCEndpointAtomicConfig
from provisioner.utils.aws import get_standard_tags

@template_registry("aws-vpc-endpoint-atomic")
class VPCEndpointAtomicTemplate(InfrastructureTemplate):
    """
    AWS VPC Endpoint Template
    """
    
    def __init__(self, name: str = None, config: Dict[str, Any] = None, **kwargs):
        raw_config = config or kwargs or {}
        self.cfg = VPCEndpointAtomicConfig(raw_config)
        
        if name is None:
            name = self.cfg.endpoint_name
            
        super().__init__(name, raw_config)
        self.vpce: Optional[aws.ec2.VpcEndpoint] = None

    def create_infrastructure(self) -> Dict[str, Any]:
        """Create VPC Endpoint directly - shows as actual AWS resource in preview"""
        tags = get_standard_tags(
            project=self.cfg.project_name,
            environment=self.cfg.environment,
            template="vpc-endpoint-atomic"
        )
        # Use pattern: aws.ec2.VpcEndpoint(f"{self.name}-vpcendpoint", ...)
        self.vpce = aws.ec2.VpcEndpoint(
            self.name,
            vpc_id=self.cfg.vpc_id,
            service_name=self.cfg.service_name,
            vpc_endpoint_type=self.cfg.vpc_endpoint_type,
            subnet_ids=self.cfg.subnet_ids,
            security_group_ids=self.cfg.security_group_ids,
            route_table_ids=self.cfg.route_table_ids,
            tags={**tags, "Name": self.cfg.endpoint_name}
        )
        
        pulumi.export("vpc_endpoint_id", self.vpce.id)
        
        return self.get_outputs()

    def get_outputs(self) -> Dict[str, Any]:
        if not self.vpce:
            return {}
        return {
            "vpc_endpoint_id": self.vpce.id,
            "vpc_endpoint_arn": self.vpce.arn
        }

    @classmethod
    def get_metadata(cls):
        return {
            "name": "vpc-endpoint-atomic",
            "title": "VPC Endpoint",
            "description": "Standalone AWS VPC Endpoint resource.",
            "category": "networking",
            "provider": "aws",
            "tier": "atomic"
        }
