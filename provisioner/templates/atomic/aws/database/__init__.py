"""
AWS Database Atomic Templates
"""
from .rds_atomic.pulumi import RDSInstanceAtomicTemplate
from .rds_subnet_group_atomic.pulumi import RDSSubnetGroupAtomicTemplate
from .dynamodb_atomic.pulumi import DynamoDBAtomicTemplate
from .aurora_cluster_atomic.pulumi import AuroraClusterAtomicTemplate
from .aurora_cluster_instance_atomic.pulumi import AuroraClusterInstanceAtomicTemplate

__all__ = [
    'RDSInstanceAtomicTemplate',
    'RDSSubnetGroupAtomicTemplate',
    'DynamoDBAtomicTemplate',
    'AuroraClusterAtomicTemplate',
    'AuroraClusterInstanceAtomicTemplate'
]
