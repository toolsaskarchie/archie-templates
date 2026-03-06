"""
Redis Non-Prod Configuration

Type-safe configuration for Redis development cluster.
"""
from typing import Any, Dict, List, Optional


class RedisNonProdConfig:
    """Configuration for Redis Non-Prod cluster"""
    
    def __init__(self, template_or_config: Any):
        """Initialize from config dictionary or template instance"""
        if hasattr(template_or_config, 'get_parameter'):
            self.template = template_or_config
            self.raw_config = self.template.config
        else:
            self.template = None
            self.raw_config = template_or_config

        self.parameters = self.raw_config.get('parameters', {}).get('aws', {}) or self.raw_config.get('parameters', {})
        
        # Meta
        self.environment = self.raw_config.get('environment', 'nonprod')
        self.region = self.raw_config.get('region', 'us-east-1')

        # Cluster settings
        self.cluster_name = self.get_parameter('cluster_name', 'redis-nonprod')
        self.engine_version = self.get_parameter('engine_version', '7.0')
        self.node_type = self.get_parameter('node_type', 'cache.t3.micro')
        self.num_cache_nodes = int(self.get_parameter('num_cache_nodes', 1))
        self.port = int(self.get_parameter('port', 6379))
        
        # Network
        self.vpc_id = self.get_parameter('vpc_id', '')
        self.subnet_ids = self.get_parameter('subnet_ids', [])
        self.allowed_cidr_blocks = self.get_parameter('allowed_cidr_blocks', ['10.0.0.0/8'])
        
        # Backup
        self.snapshot_retention_limit = int(self.get_parameter('snapshot_retention_limit', 5))
        self.snapshot_window = self.get_parameter('snapshot_window', '03:00-05:00')
        self.maintenance_window = self.get_parameter('maintenance_window', 'sun:05:00-sun:06:00')
        
        # Multi-AZ
        self.multi_az_enabled = self.get_parameter('multi_az_enabled', False)
        
        # Tags
        self.project = self.get_parameter('project') or self.raw_config.get('projectName') or ""

    def get_parameter(self, key: str, default: Any = None) -> Any:
        """Get a parameter from the configuration."""
        if self.template:
            return self.template.get_parameter(key, default)
        return self.parameters.get(key, default)
    
    @property
    def resource_tags(self) -> Dict[str, str]:
        """Get resource tags"""
        tags = {
            'Environment': self.environment,
            'ManagedBy': 'Archie',
            'Service': 'ElastiCache',
            'Engine': 'Redis'
        }
        if self.project:
            tags['Project'] = self.project
        return tags
    
    @property
    def az_mode(self) -> str:
        """Get AZ mode based on multi-AZ setting"""
        return 'cross-az' if self.multi_az_enabled and self.num_cache_nodes > 1 else 'single-az'

    @staticmethod
    def get_config_schema() -> Dict[str, Any]:
        """Get JSON schema for UI configuration."""
        from provisioner.templates.shared.aws_schema import (
            get_project_env_schema,
            get_networking_schema,
            get_cache_selection_schema,
            get_security_connectivity_schema,
            get_observability_schema
        )
        return {
            "type": "object",
            "properties": {
                **get_project_env_schema(order_offset=0),
                **get_networking_schema(allow_new=True, allow_existing=True, order_offset=10),
                **get_cache_selection_schema(engine="redis", order_offset=80),
                **get_security_connectivity_schema(include_rdp=False, order_offset=150),
                **get_observability_schema(order_offset=200),
            },
            "required": ["project_name", "region", "cluster_name"]
        }
