"""AWS ElastiCache Cluster Atomic Configuration"""
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

@dataclass
class ElastiCacheClusterAtomicConfig:
    cluster_id: str
    engine: str
    node_type: str
    num_cache_nodes: int
    project_name: str
    environment: str
    region: str
    engine_version: Optional[str] = None
    parameter_group_name: Optional[str] = None
    subnet_group_name: Optional[str] = None
    security_group_ids: Optional[List[str]] = None
    port: Optional[int] = None
    az_mode: Optional[str] = None
    snapshot_retention_limit: Optional[int] = None
    snapshot_window: Optional[str] = None
    maintenance_window: Optional[str] = None
    tags: Optional[Dict[str, str]] = None
    
    def __init__(self, config: Dict[str, Any]):
        aws_params = config.get('parameters', {}).get('aws', {})
        self.project_name = aws_params.get('project_name', 'my-project')
        self.environment = aws_params.get('environment', 'dev')
        self.region = aws_params.get('region', 'us-east-1')
        self.cluster_id = aws_params.get('cluster_id', f"{self.project_name}-{self.environment}-cache")
        self.engine = aws_params.get('engine', 'redis')
        self.engine_version = aws_params.get('engine_version', '7.0')
        self.node_type = aws_params.get('node_type', 'cache.t3.micro')
        self.num_cache_nodes = aws_params.get('num_cache_nodes', 1)
        self.parameter_group_name = aws_params.get('parameter_group_name')
        self.subnet_group_name = aws_params.get('subnet_group_name')
        self.security_group_ids = aws_params.get('security_group_ids', [])
        self.port = aws_params.get('port')
        self.az_mode = aws_params.get('az_mode', 'single-az')
        self.snapshot_retention_limit = aws_params.get('snapshot_retention_limit', 5)
        self.snapshot_window = aws_params.get('snapshot_window', '03:00-05:00')
        self.maintenance_window = aws_params.get('maintenance_window', 'sun:05:00-sun:06:00')
        self.tags = aws_params.get('tags', {})
        
        # Collect all extra kwargs for the component
        self.extra_args = {k: v for k, v in aws_params.items() if k not in [
            'project_name', 'environment', 'region', 'cluster_id', 'engine',
            'engine_version', 'node_type', 'num_cache_nodes', 'parameter_group_name',
            'subnet_group_name', 'security_group_ids', 'port', 'az_mode',
            'snapshot_retention_limit', 'snapshot_window', 'maintenance_window', 'tags'
        ]}
