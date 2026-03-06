"""
AWS Subnet Template
Creates a standalone AWS Subnet using the SubnetComponent.
"""
from typing import Any, Dict, Optional
import pulumi
import pulumi_aws as aws

from provisioner.templates.base import template_registry, InfrastructureTemplate
from .config import SubnetAtomicConfig
from provisioner.utils.aws import get_standard_tags

@template_registry("aws-subnet-atomic")
class SubnetAtomicTemplate(InfrastructureTemplate):
    """
    AWS Subnet Template
    """
    
    def __init__(self, name: str = None, config: Dict[str, Any] = None, **kwargs):
        raw_config = config or kwargs or {}
        self.cfg = SubnetAtomicConfig(raw_config)
        
        if name is None:
            name = self.cfg.subnet_name
            
        super().__init__(name, raw_config)
        self.subnet: Optional[aws.ec2.Subnet] = None

    def create_infrastructure(self) -> Dict[str, Any]:
        """Create Subnet directly - shows as actual AWS resource in preview"""
        tags = get_standard_tags(
            project=self.cfg.project_name,
            environment=self.cfg.environment,
            template="subnet-atomic"
        )
        # Use pattern: aws.ec2.Subnet(f"{self.name}-subnet", ...)
        self.subnet = aws.ec2.Subnet(
            self.name,
            vpc_id=self.cfg.vpc_id,
            cidr_block=self.cfg.cidr_block,
            availability_zone=self.cfg.availability_zone,
            map_public_ip_on_launch=self.cfg.map_public_ip_on_launch,
            tags={**tags, "Name": self.cfg.subnet_name}
        )
        
        pulumi.export("subnet_id", self.subnet.id)
        pulumi.export("subnet_arn", self.subnet.arn)
        
        return self.get_outputs()

    def get_outputs(self) -> Dict[str, Any]:
        if not self.subnet:
            return {}
        return {
            "subnet_id": self.subnet.id,
            "subnet_arn": self.subnet.arn,
            "cidr_block": self.subnet.cidr_block,
            "az": self.subnet.availability_zone
        }

    @classmethod
    def get_metadata(cls):
        return {
            "name": "subnet-atomic",
            "title": "Subnet",
            "description": "Standalone AWS Subnet resource.",
            "category": "networking",
            "provider": "aws",
            "tier": "atomic"
        }
