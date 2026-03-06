"""
ElastiCache Subnet Group Template

AWS ElastiCache subnet group for placing cache clusters in specific subnets.
Uses direct AWS resources.
"""
from typing import Any, Dict, List
import pulumi
import pulumi_aws as aws

from provisioner.templates.atomic.base import AtomicTemplate


class ElastiCacheSubnetGroupAtomicTemplate(AtomicTemplate):
    """
    ElastiCache Subnet Group - Creates subnet group directly
    
    Configuration:
        name: Subnet group name
        description: Subnet group description
        subnet_ids: List of subnet IDs
        tags: Resource tags
    
    Outputs:
        name: Subnet group name
        id: Subnet group ID
        arn: Subnet group ARN
        subnet_ids: List of subnet IDs
    """
    
    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.subnet_group: aws.elasticache.SubnetGroup = None
    
    def create_infrastructure(self) -> Dict[str, Any]:
        """Create ElastiCache subnet group directly - shows as actual AWS resource in preview"""
        
        subnet_ids = self.config.get('subnet_ids', [])
        
        if not subnet_ids:
            raise ValueError("subnet_ids is required for ElastiCache subnet group")
        
        # Create subnet group directly (no ComponentResource wrapper)
        self.subnet_group = aws.elasticache.SubnetGroup(
            f"{self.name}-subnet-group",
            name=self.config.get('name', self.name),
            subnet_ids=subnet_ids,
            description=self.config.get('description', f'Subnet group for {self.name}'),
            tags=self.config.get('tags', {})
        )
        
        return {
            'name': self.subnet_group.name,
            'id': self.subnet_group.id,
            'arn': self.subnet_group.arn,
            'subnet_ids': self.subnet_group.subnet_ids
        }
