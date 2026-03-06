"""
ElastiCache Cluster Template

AWS ElastiCache cluster for Redis or Memcached caching solutions.
Supports single-node and cluster mode configurations. Uses direct AWS resources.
"""
from typing import Any, Dict
import pulumi
import pulumi_aws as aws

from provisioner.templates.atomic.base import AtomicTemplate


class ElastiCacheClusterAtomicTemplate(AtomicTemplate):
    """
    ElastiCache Cluster - Creates managed Redis/Memcached cluster directly
    
    Configuration:
        cluster_id: Unique cluster identifier
        engine: redis or memcached
        engine_version: Engine version (e.g., "7.0")
        node_type: Instance type (e.g., cache.t3.micro)
        num_cache_nodes: Number of cache nodes
        parameter_group_name: Parameter group name
        subnet_group_name: Subnet group name
        security_group_ids: List of security group IDs
        port: Port number (default 6379 for Redis)
        az_mode: single-az or cross-az
        snapshot_retention_limit: Backup retention in days
        snapshot_window: Backup window (HH:MM-HH:MM UTC)
        maintenance_window: Maintenance window
        tags: Resource tags
    
    Outputs:
        cluster_id: Cluster identifier
        endpoint: Primary endpoint address
        port: Cluster port
        arn: Cluster ARN
        cache_nodes: List of cache nodes
    """
    
    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.cluster: aws.elasticache.Cluster = None
    
    def create_infrastructure(self) -> Dict[str, Any]:
        """Create ElastiCache cluster directly - shows as actual AWS resource in preview"""
        
        # Create ElastiCache cluster directly (no ComponentResource wrapper)
        self.cluster = aws.elasticache.Cluster(
            f"{self.name}-cluster",
            cluster_id=self.config.get('cluster_id', self.name),
            engine=self.config.get('engine', 'redis'),
            engine_version=self.config.get('engine_version', '7.0'),
            node_type=self.config.get('node_type', 'cache.t3.micro'),
            num_cache_nodes=self.config.get('num_cache_nodes', 1),
            parameter_group_name=self.config.get('parameter_group_name'),
            subnet_group_name=self.config.get('subnet_group_name'),
            security_group_ids=self.config.get('security_group_ids', []),
            port=self.config.get('port'),
            az_mode=self.config.get('az_mode', 'single-az'),
            snapshot_retention_limit=self.config.get('snapshot_retention_limit', 5),
            snapshot_window=self.config.get('snapshot_window', '03:00-05:00'),
            maintenance_window=self.config.get('maintenance_window', 'sun:05:00-sun:06:00'),
            tags=self.config.get('tags', {})
        )
        
        return {
            'cluster_id': self.cluster.cluster_id,
            'endpoint': self.cluster.cache_nodes[0].address,
            'port': self.cluster.port,
            'arn': self.cluster.arn,
            'cache_nodes': self.cluster.cache_nodes
        }
