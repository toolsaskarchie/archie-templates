"""
Azure Cache for Redis Non-Prod Template

Cost-optimized Redis cache for dev/staging environments.
Basic tier with 250MB capacity, TLS enforcement, and non-SSL port disabled.

Base cost (~$16/mo):
- 1 Redis Cache (Basic C0, 250MB)
- TLS 1.2 minimum enforced
- Non-SSL port disabled by default
- Azure-managed patching
- Optional firewall rules
"""

from typing import Any, Dict, Optional
from pathlib import Path
import pulumi
import pulumi_azure_native as azure_native

from provisioner.templates.base import InfrastructureTemplate, template_registry
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory
from provisioner.utils.azure.tags import get_standard_tags
from provisioner.utils.azure.naming import get_resource_name


@template_registry("azure-redis-nonprod")
class AzureRedisNonProdTemplate(InfrastructureTemplate):
    """
    Azure Cache for Redis Non-Prod Template

    Cost-optimized Redis cache for non-production environments.
    Basic tier with 250MB capacity and TLS enforcement.
    """

    def __init__(self, name: str = None, config: Dict[str, Any] = None, azure_config: Dict[str, Any] = None, **kwargs):
        """Initialize Azure Redis Non-Prod template"""
        raw_config = config or azure_config or kwargs or {}

        if name is None:
            name = (
                raw_config.get('project_name') or
                raw_config.get('projectName') or
                raw_config.get('parameters', {}).get('azure', {}).get('project_name') or
                'azure-redis-nonprod'
            )

        super().__init__(name, raw_config)
        self.config = raw_config

        # Resource references (populated in create())
        self.resource_group: Optional[object] = None
        self.redis_cache: Optional[object] = None
        self.firewall_rule: Optional[object] = None

    def _cfg(self, key: str, default=None):
        """Read config from root, parameters.azure, or parameters (Rule #6)"""
        params = self.config.get('parameters', {})
        azure_params = params.get('azure', {}) if isinstance(params, dict) else {}
        return (
            self.config.get(key) or
            (azure_params.get(key) if isinstance(azure_params, dict) else None) or
            (params.get(key) if isinstance(params, dict) else None) or
            default
        )

    def create_infrastructure(self) -> Dict[str, Any]:
        """Deploy Redis infrastructure (implements abstract method)"""
        return self.create()

    def create(self) -> Dict[str, Any]:
        """Deploy complete Azure Redis infrastructure"""

        # Read config
        project = self._cfg('project_name', 'myapp')
        env = self._cfg('environment', 'dev')
        location = self._cfg('location', 'eastus')
        team_name = self._cfg('team_name', '')
        sku_name = self._cfg('sku_name', 'Basic')
        sku_family = self._cfg('sku_family', 'C')
        sku_capacity = int(self._cfg('sku_capacity', '0'))
        redis_version = self._cfg('redis_version', '6')
        minimum_tls_version = self._cfg('minimum_tls_version', '1.2')

        enable_non_ssl_port = self._cfg('enable_non_ssl_port', False)
        if isinstance(enable_non_ssl_port, str):
            enable_non_ssl_port = enable_non_ssl_port.lower() in ('true', '1', 'yes')

        client_ip = self._cfg('client_ip', '')

        # Standard tags
        tags = get_standard_tags(project=project, environment=env)
        tags['ManagedBy'] = 'Archie'
        tags['Template'] = 'azure-redis-nonprod'
        tags.update(self._cfg('tags', {}))
        if team_name:
            tags['Team'] = team_name

        # Resource names (prefer injected on upgrade — Rule #3)
        rg_name = self._cfg('resource_group_name') or f'rg-{project}-{env}-redis'
        cache_name = self._cfg('redis_cache_name') or f'redis-{project}-{env}'

        # =================================================================
        # LAYER 1: Resource Group
        # =================================================================

        self.resource_group = factory.create(
            'azure-native:resources:ResourceGroup', rg_name,
            resource_group_name=rg_name,
            location=location,
            tags={**tags, 'Purpose': 'redis-cache'},
        )

        # =================================================================
        # LAYER 2: Redis Cache
        # =================================================================

        redis_config = {
            'maxmemory-policy': self._cfg('maxmemory_policy', 'volatile-lru'),
        }

        self.redis_cache = factory.create(
            'azure-native:cache:Redis', cache_name,
            name=cache_name,
            resource_group_name=self.resource_group.name,
            location=location,
            sku={
                'name': sku_name,
                'family': sku_family,
                'capacity': sku_capacity,
            },
            enable_non_ssl_port=enable_non_ssl_port,
            minimum_tls_version=minimum_tls_version,
            redis_version=redis_version,
            redis_configuration=redis_config,
            public_network_access='Enabled',
            tags=tags,
        )

        # =================================================================
        # LAYER 3: Firewall Rule (optional)
        # =================================================================

        if client_ip:
            self.firewall_rule = factory.create(
                'azure-native:cache:FirewallRule', f'{cache_name}-client',
                rule_name='ClientIP',
                cache_name=self.redis_cache.name,
                resource_group_name=self.resource_group.name,
                start_ip=client_ip,
                end_ip=client_ip,
            )

        # =================================================================
        # Exports (Rule #2, #7)
        # =================================================================

        pulumi.export('resource_group_name', rg_name)
        pulumi.export('redis_cache_name', cache_name)
        pulumi.export('redis_cache_id', self.redis_cache.id)
        pulumi.export('redis_hostname', self.redis_cache.host_name)
        pulumi.export('redis_ssl_port', self.redis_cache.ssl_port)
        pulumi.export('redis_port', self.redis_cache.port)
        pulumi.export('redis_connection_string', pulumi.Output.concat(
            cache_name, '.redis.cache.windows.net:6380,password=',
            self.redis_cache.access_keys.apply(
                lambda keys: keys.primary_key if keys else ''
            ) if hasattr(self.redis_cache, 'access_keys') else '',
            ',ssl=True,abortConnect=False'
        ))
        pulumi.export('environment', env)
        if team_name:
            pulumi.export('team_name', team_name)

        return self.get_outputs()

    def get_outputs(self) -> Dict[str, Any]:
        """Get outputs for downstream templates"""
        return {
            'resource_group_name': self.resource_group.name if self.resource_group else None,
            'redis_cache_name': self.redis_cache.name if self.redis_cache else None,
            'redis_cache_id': self.redis_cache.id if self.redis_cache else None,
            'redis_hostname': self.redis_cache.host_name if self.redis_cache else None,
            'redis_ssl_port': self.redis_cache.ssl_port if self.redis_cache else None,
            'redis_port': self.redis_cache.port if self.redis_cache else None,
        }

    @classmethod
    def get_metadata(cls) -> Dict[str, Any]:
        """Template metadata for catalog UI"""
        return {
            "name": "azure-redis-nonprod",
            "title": "Redis Cache (Basic)",
            "description": "Cost-optimized Azure Cache for Redis. Basic tier with 250MB, TLS 1.2 enforcement, and configurable eviction policy. For dev/staging caching.",
            "category": "database",
            "version": "1.0.0",
            "author": "Archie",
            "cloud": "azure",
            "environment": "nonprod",
            "base_cost": "$16/month",
            "features": [
                "Basic C0 tier with 250MB capacity",
                "TLS 1.2 minimum enforced (non-SSL port disabled)",
                "Redis 6.x with configurable eviction policy",
                "Azure-managed patching and maintenance",
                "Optional firewall rules for IP-based access control",
                "Connection string exported for app configuration",
                "Standard tagging and naming conventions",
            ],
            "tags": ["azure", "redis", "cache", "database", "nonprod"],
            "deployment_time": "10-15 minutes",
            "complexity": "beginner",
            "use_cases": [
                "Session caching for web applications",
                "API response caching",
                "Pub/Sub messaging for microservices",
                "Rate limiting and throttling",
                "Development and testing cache layer",
            ],
            "pillars": [
                {
                    "title": "Security",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "TLS encryption enforced, non-SSL port disabled, firewall rules available",
                    "practices": [
                        "TLS 1.2 minimum enforced for all connections",
                        "Non-SSL port (6379) disabled by default",
                        "Access key authentication required",
                        "Optional IP-based firewall rules",
                        "Public network access can be restricted",
                    ]
                },
                {
                    "title": "Operational Excellence",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Azure-managed service with automated patching and standard tagging",
                    "practices": [
                        "Azure-managed patching and maintenance windows",
                        "Infrastructure as Code with Pulumi for repeatable deployments",
                        "Connection string exported for easy app integration",
                        "Standard resource naming and tagging conventions",
                    ]
                },
                {
                    "title": "Reliability",
                    "score": "needs-improvement",
                    "score_color": "#ef4444",
                    "description": "Basic tier has no SLA and no replication (suitable for non-production only)",
                    "practices": [
                        "Basic tier is single-node with no replication",
                        "No SLA for Basic tier (upgrade to Standard for 99.9%)",
                        "Azure-managed failover for Standard/Premium tiers",
                        "Suitable for dev/test workloads where data loss is acceptable",
                    ]
                },
                {
                    "title": "Cost Optimization",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Smallest available tier at ~$16/month for non-production workloads",
                    "practices": [
                        "Basic C0 tier is the lowest-cost Redis option (~$16/mo)",
                        "250MB capacity sufficient for development caching",
                        "No replication overhead (single node)",
                        "Pay only for provisioned capacity",
                    ]
                },
                {
                    "title": "Sustainability",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Minimal resource footprint with right-sized capacity",
                    "practices": [
                        "Smallest available cache size minimizes resource consumption",
                        "Single-node deployment reduces infrastructure footprint",
                        "Azure-managed infrastructure benefits from datacenter efficiency",
                    ]
                },
            ],
        }

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        """Configuration schema for deploy form"""
        return {
            "type": "object",
            "properties": {
                "project_name": {
                    "type": "string",
                    "default": "myapp",
                    "title": "Project Name",
                    "description": "Used in resource naming (resource group, cache name)",
                    "order": 1,
                    "group": "Essentials",
                    "isEssential": True,
                },
                "environment": {
                    "type": "string",
                    "default": "dev",
                    "title": "Environment",
                    "description": "Deployment environment",
                    "enum": ["dev", "staging", "uat"],
                    "order": 2,
                    "group": "Essentials",
                    "isEssential": True,
                },
                "location": {
                    "type": "string",
                    "default": "eastus",
                    "title": "Azure Region",
                    "description": "Azure region for all resources",
                    "enum": ["eastus", "eastus2", "westus2", "westeurope", "northeurope", "southeastasia", "australiaeast"],
                    "order": 3,
                    "group": "Essentials",
                    "isEssential": True,
                },
                "sku_name": {
                    "type": "string",
                    "default": "Basic",
                    "title": "Cache Tier",
                    "description": "Redis cache tier (Basic = no SLA, Standard = 99.9% SLA with replication)",
                    "enum": ["Basic", "Standard"],
                    "order": 10,
                    "group": "Cache Configuration",
                    "cost_impact": "Basic ~$16/mo, Standard ~$40/mo",
                },
                "sku_capacity": {
                    "type": "number",
                    "default": 0,
                    "title": "Cache Size",
                    "description": "Cache capacity (C0=250MB, C1=1GB, C2=2.5GB, C3=6GB)",
                    "enum": [0, 1, 2, 3],
                    "order": 11,
                    "group": "Cache Configuration",
                    "cost_impact": "C0 ~$16/mo, C1 ~$40/mo",
                },
                "redis_version": {
                    "type": "string",
                    "default": "6",
                    "title": "Redis Version",
                    "description": "Redis engine version",
                    "enum": ["6"],
                    "order": 12,
                    "group": "Cache Configuration",
                },
                "maxmemory_policy": {
                    "type": "string",
                    "default": "volatile-lru",
                    "title": "Eviction Policy",
                    "description": "How Redis handles memory limits",
                    "enum": ["volatile-lru", "allkeys-lru", "volatile-random", "allkeys-random", "volatile-ttl", "noeviction"],
                    "order": 13,
                    "group": "Cache Configuration",
                },
                "enable_non_ssl_port": {
                    "type": "boolean",
                    "default": False,
                    "title": "Enable Non-SSL Port (6379)",
                    "description": "Allow unencrypted connections on port 6379 (not recommended)",
                    "order": 20,
                    "group": "Security & Access",
                },
                "minimum_tls_version": {
                    "type": "string",
                    "default": "1.2",
                    "title": "Minimum TLS Version",
                    "description": "Minimum TLS version for encrypted connections",
                    "enum": ["1.0", "1.1", "1.2"],
                    "order": 21,
                    "group": "Security & Access",
                },
                "client_ip": {
                    "type": "string",
                    "default": "",
                    "title": "Client IP Address",
                    "description": "IP address for firewall rule (e.g. 203.0.113.45). Leave blank for no firewall rule.",
                    "order": 22,
                    "group": "Security & Access",
                },
                "team_name": {
                    "type": "string",
                    "default": "",
                    "title": "Team Name",
                    "description": "Team that owns this resource",
                    "order": 50,
                    "group": "Tags",
                },
            },
            "required": ["project_name"],
        }
