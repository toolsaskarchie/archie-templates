"""
GCP Memorystore Redis Non-Prod Template

Cost-optimized managed Redis instance for development and testing:
- Memorystore Redis with configurable memory size
- Private network connectivity (VPC peering)
- BASIC tier (no replication) for cost savings
- Redis 7.0 with configurable eviction policy

Base cost (~$36/mo):
- 1 GB BASIC tier instance
- No replica (single node)
- Private service access included
"""

from typing import Any, Dict, Optional
import pulumi
import pulumi_gcp as gcp

from provisioner.templates.base import InfrastructureTemplate, template_registry
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory


@template_registry("gcp-redis-nonprod")
class RedisNonprodTemplate(InfrastructureTemplate):
    """
    GCP Memorystore Redis Non-Prod Template

    Deploys a managed Redis instance with private networking
    for non-production caching and session storage workloads.
    """

    def __init__(self, name: str = None, config: Dict[str, Any] = None, gcp_config: Dict[str, Any] = None, **kwargs):
        """Initialize Redis Non-Prod template"""
        raw_config = config or gcp_config or kwargs or {}

        if name is None:
            name = (
                raw_config.get('project_name') or
                raw_config.get('projectName') or
                raw_config.get('parameters', {}).get('gcp', {}).get('project_name') or
                'redis-nonprod'
            )

        super().__init__(name, raw_config)
        self.config = raw_config

        # Resource references
        self.redis_instance: Optional[object] = None
        self.firewall_redis: Optional[object] = None

    def _cfg(self, key: str, default=None):
        """Read config from root, parameters.gcp, or parameters (Rule #6)"""
        params = self.config.get('parameters', {})
        gcp_params = params.get('gcp', {}) if isinstance(params, dict) else {}
        return (
            self.config.get(key) or
            (gcp_params.get(key) if isinstance(gcp_params, dict) else None) or
            (params.get(key) if isinstance(params, dict) else None) or
            default
        )

    def create_infrastructure(self) -> Dict[str, Any]:
        """Deploy Redis infrastructure (implements abstract method)"""
        return self.create()

    def create(self) -> Dict[str, Any]:
        """Deploy complete Memorystore Redis infrastructure"""

        # Read config
        project_name = self._cfg('project_name', 'redis')
        environment = self._cfg('environment', 'dev')
        team_name = self._cfg('team_name', '')
        gcp_project = self._cfg('gcp_project', '')
        region = self._cfg('region', 'us-central1')
        network = self._cfg('network', 'default')

        # Redis config
        memory_size_gb = int(self._cfg('memory_size_gb', 1))
        redis_version = self._cfg('redis_version', 'REDIS_7_0')
        tier = self._cfg('tier', 'BASIC')
        display_name = self._cfg('display_name', f'{project_name} Redis ({environment})')

        # Redis settings
        eviction_policy = self._cfg('eviction_policy', 'volatile-lru')
        maxmemory_policy = self._cfg('maxmemory_policy', 'volatile-lru')
        notify_keyspace_events = self._cfg('notify_keyspace_events', '')

        # Auth
        enable_auth = self._cfg('enable_auth', True)
        if isinstance(enable_auth, str):
            enable_auth = enable_auth.lower() in ('true', '1', 'yes')

        # Transit encryption
        enable_transit_encryption = self._cfg('enable_transit_encryption', False)
        if isinstance(enable_transit_encryption, str):
            enable_transit_encryption = enable_transit_encryption.lower() in ('true', '1', 'yes')

        # Maintenance window
        maintenance_day = self._cfg('maintenance_day', 'SUNDAY')
        maintenance_hour = int(self._cfg('maintenance_hour', 4))

        # Standard GCP labels
        labels = {
            'project': project_name,
            'environment': environment,
            'template': 'gcp-redis-nonprod',
            'managed-by': 'archie',
        }
        if team_name:
            labels['team'] = team_name.lower().replace(' ', '-')
        labels.update(self._cfg('labels', {}))

        resource_name = f"{project_name}-{environment}"
        instance_name = self._cfg('instance_name', f"{resource_name}-redis")

        # =================================================================
        # LAYER 1: Redis Config
        # =================================================================

        redis_configs = {}
        if maxmemory_policy:
            redis_configs['maxmemory-policy'] = maxmemory_policy
        if notify_keyspace_events:
            redis_configs['notify-keyspace-events'] = notify_keyspace_events

        # =================================================================
        # LAYER 2: Memorystore Redis Instance
        # =================================================================

        # Build the authorized network path
        authorized_network = f"projects/{gcp_project}/global/networks/{network}" if gcp_project else f"projects/default/global/networks/{network}"

        self.redis_instance = gcp.redis.Instance(
            instance_name,
            name=instance_name,
            project=gcp_project if gcp_project else None,
            region=region,
            tier=tier,
            memory_size_gb=memory_size_gb,
            redis_version=redis_version,
            display_name=display_name,
            authorized_network=authorized_network,
            connect_mode="PRIVATE_SERVICE_ACCESS",
            auth_enabled=enable_auth,
            transit_encryption_mode="SERVER_AUTHENTICATION" if enable_transit_encryption else "DISABLED",
            redis_configs=redis_configs if redis_configs else None,
            labels=labels,
            maintenance_policy={
                "weekly_maintenance_windows": [{
                    "day": maintenance_day,
                    "start_time": {
                        "hours": maintenance_hour,
                        "minutes": 0,
                        "seconds": 0,
                        "nanos": 0,
                    },
                }],
            },
        )

        # =================================================================
        # LAYER 3: Firewall Rule for Redis Access
        # =================================================================

        self.firewall_redis = gcp.compute.Firewall(
            f"{resource_name}-allow-redis",
            name=f"{resource_name}-allow-redis",
            project=gcp_project if gcp_project else None,
            network=network,
            direction="INGRESS",
            source_tags=[f"{resource_name}-app"],
            target_tags=[f"{resource_name}-redis"],
            allows=[{
                "protocol": "tcp",
                "ports": ["6379"],
            }],
            description=f"Allow Redis access from {resource_name} app tier",
        )

        # =================================================================
        # Exports (Rule #2, #7)
        # =================================================================

        pulumi.export('redis_instance_name', self.redis_instance.name)
        pulumi.export('redis_instance_id', self.redis_instance.id)
        pulumi.export('redis_host', self.redis_instance.host)
        pulumi.export('redis_port', self.redis_instance.port)
        pulumi.export('redis_current_location_id', self.redis_instance.current_location_id)
        pulumi.export('redis_memory_size_gb', memory_size_gb)
        pulumi.export('redis_version', redis_version)
        pulumi.export('redis_tier', tier)
        pulumi.export('redis_auth_enabled', str(enable_auth))

        if enable_auth:
            pulumi.export('redis_auth_string', self.redis_instance.auth_string)

        pulumi.export('redis_connection_string', pulumi.Output.concat(
            'redis://', self.redis_instance.host, ':', self.redis_instance.port.apply(str),
        ))
        pulumi.export('region', region)
        pulumi.export('environment', environment)

        return self.get_outputs()

    def get_outputs(self) -> Dict[str, Any]:
        """Get outputs for this template"""
        outputs = {
            "redis_instance_name": self.redis_instance.name if self.redis_instance else None,
            "redis_instance_id": self.redis_instance.id if self.redis_instance else None,
            "redis_host": self.redis_instance.host if self.redis_instance else None,
            "redis_port": self.redis_instance.port if self.redis_instance else None,
            "redis_current_location_id": self.redis_instance.current_location_id if self.redis_instance else None,
        }
        return outputs

    @classmethod
    def get_metadata(cls) -> Dict[str, Any]:
        """Template metadata for the catalog UI"""
        return {
            "name": "gcp-redis-nonprod",
            "title": "Memorystore Redis",
            "description": "Managed Redis instance with private networking, authentication, and configurable eviction for non-production caching workloads.",
            "category": "database",
            "version": "1.0.0",
            "author": "Archie",
            "cloud": "gcp",
            "environment": "nonprod",
            "base_cost": "$36/month",
            "features": [
                "Memorystore Redis 7.0 managed instance",
                "Private network connectivity via VPC peering",
                "BASIC tier (single node) for cost savings",
                "Configurable memory size (1-300 GB)",
                "AUTH token authentication enabled by default",
                "Configurable eviction policy (volatile-lru default)",
                "Scheduled maintenance window (Sundays at 4 AM)",
                "Optional transit encryption (TLS)",
                "Firewall rule for app-tier access",
            ],
            "tags": ["gcp", "redis", "memorystore", "cache", "database", "nonprod"],
            "deployment_time": "5-10 minutes",
            "complexity": "beginner",
            "use_cases": [
                "Application session storage",
                "API response caching",
                "Rate limiting and throttling",
                "Real-time leaderboards and counters",
                "Pub/Sub messaging for microservices",
            ],
            "pillars": [
                {
                    "title": "Operational Excellence",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Fully managed Redis with automated maintenance and monitoring",
                    "practices": [
                        "Infrastructure as Code with Pulumi for repeatable deployments",
                        "Managed service handles patching and version upgrades",
                        "Scheduled maintenance window minimizes disruption",
                        "Built-in monitoring via Cloud Monitoring integration",
                        "Connection string exported for immediate application use",
                    ],
                },
                {
                    "title": "Security",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Private networking with AUTH and optional TLS encryption",
                    "practices": [
                        "Private Service Access — no public IP exposure",
                        "AUTH token required for client connections by default",
                        "Optional transit encryption (TLS) for data in motion",
                        "Firewall rule scoped to app-tier network tags only",
                        "VPC peering ensures traffic stays on Google network",
                    ],
                },
                {
                    "title": "Reliability",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "BASIC tier suitable for non-production with managed infrastructure",
                    "practices": [
                        "Google-managed infrastructure with automatic failover (STANDARD tier)",
                        "BASIC tier appropriate for dev/test where HA is not required",
                        "Configurable eviction policy prevents OOM crashes",
                        "Automated maintenance during low-traffic windows",
                    ],
                },
                {
                    "title": "Performance Efficiency",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Sub-millisecond latency with configurable memory and eviction",
                    "practices": [
                        "In-memory data store provides sub-millisecond read latency",
                        "Configurable memory size from 1 GB to 300 GB",
                        "Eviction policy tuning for workload-specific cache behavior",
                        "Private networking minimizes client-to-server latency",
                    ],
                },
                {
                    "title": "Cost Optimization",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "BASIC tier with minimum memory for non-production workloads",
                    "practices": [
                        "BASIC tier avoids replica costs for dev/test",
                        "1 GB default minimizes hourly charges",
                        "No persistent disk costs — memory-only storage",
                        "Right-sized for non-production cache workloads",
                    ],
                },
                {
                    "title": "Sustainability",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Right-sized managed service reduces infrastructure waste",
                    "practices": [
                        "Single-node deployment avoids redundant compute for non-production",
                        "Managed service shares underlying infrastructure efficiently",
                        "Memory-only storage avoids unnecessary disk I/O",
                        "Google Cloud carbon-neutral infrastructure",
                    ],
                },
            ],
        }

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        """Configuration schema for the deploy form"""
        return {
            "type": "object",
            "properties": {
                "project_name": {
                    "type": "string",
                    "default": "myproject",
                    "title": "Project Name",
                    "description": "Used in resource naming (lowercase, no spaces)",
                    "order": 1,
                    "group": "Essentials",
                    "isEssential": True,
                },
                "environment": {
                    "type": "string",
                    "default": "dev",
                    "title": "Environment",
                    "description": "Deployment environment",
                    "enum": ["dev", "staging", "prod"],
                    "order": 2,
                    "group": "Essentials",
                    "isEssential": True,
                },
                "region": {
                    "type": "string",
                    "default": "us-central1",
                    "title": "GCP Region",
                    "description": "Region for the Redis instance",
                    "enum": ["us-central1", "us-east1", "us-west1", "europe-west1", "asia-east1"],
                    "order": 3,
                    "group": "Essentials",
                    "isEssential": True,
                },
                "gcp_project": {
                    "type": "string",
                    "default": "",
                    "title": "GCP Project ID",
                    "description": "Google Cloud project ID (leave empty to use default)",
                    "order": 4,
                    "group": "Essentials",
                    "isEssential": True,
                },
                "memory_size_gb": {
                    "type": "number",
                    "default": 1,
                    "title": "Memory Size (GB)",
                    "description": "Redis instance memory in gigabytes",
                    "minimum": 1,
                    "maximum": 300,
                    "order": 10,
                    "group": "Redis Configuration",
                    "isEssential": True,
                    "cost_impact": "1 GB BASIC: ~$36/mo, 5 GB: ~$183/mo",
                },
                "redis_version": {
                    "type": "string",
                    "default": "REDIS_7_0",
                    "title": "Redis Version",
                    "description": "Memorystore Redis engine version",
                    "enum": ["REDIS_6_X", "REDIS_7_0", "REDIS_7_2"],
                    "order": 11,
                    "group": "Redis Configuration",
                },
                "tier": {
                    "type": "string",
                    "default": "BASIC",
                    "title": "Instance Tier",
                    "description": "BASIC (single node) or STANDARD_HA (with replica)",
                    "enum": ["BASIC", "STANDARD_HA"],
                    "order": 12,
                    "group": "Redis Configuration",
                    "cost_impact": "STANDARD_HA doubles cost (adds replica)",
                },
                "instance_name": {
                    "type": "string",
                    "default": "",
                    "title": "Instance Name",
                    "description": "Custom Redis instance name (defaults to project-env-redis)",
                    "order": 13,
                    "group": "Redis Configuration",
                },
                "display_name": {
                    "type": "string",
                    "default": "",
                    "title": "Display Name",
                    "description": "Human-readable name shown in GCP Console",
                    "order": 14,
                    "group": "Redis Configuration",
                },
                "maxmemory_policy": {
                    "type": "string",
                    "default": "volatile-lru",
                    "title": "Eviction Policy",
                    "description": "How Redis evicts keys when memory is full",
                    "enum": ["volatile-lru", "allkeys-lru", "volatile-random", "allkeys-random", "volatile-ttl", "noeviction"],
                    "order": 15,
                    "group": "Redis Configuration",
                },
                "network": {
                    "type": "string",
                    "default": "default",
                    "title": "VPC Network",
                    "description": "VPC network for private connectivity",
                    "order": 20,
                    "group": "Network Configuration",
                },
                "enable_auth": {
                    "type": "boolean",
                    "default": True,
                    "title": "Enable AUTH",
                    "description": "Require AUTH token for Redis connections",
                    "order": 30,
                    "group": "Security & Access",
                },
                "enable_transit_encryption": {
                    "type": "boolean",
                    "default": False,
                    "title": "Enable Transit Encryption",
                    "description": "Encrypt data in transit with TLS (adds slight latency)",
                    "order": 31,
                    "group": "Security & Access",
                },
                "maintenance_day": {
                    "type": "string",
                    "default": "SUNDAY",
                    "title": "Maintenance Day",
                    "description": "Day of week for maintenance window",
                    "enum": ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"],
                    "order": 40,
                    "group": "Maintenance",
                },
                "maintenance_hour": {
                    "type": "number",
                    "default": 4,
                    "title": "Maintenance Hour (UTC)",
                    "description": "Hour of day (UTC) for maintenance window start",
                    "minimum": 0,
                    "maximum": 23,
                    "order": 41,
                    "group": "Maintenance",
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
            "required": ["project_name", "region"],
        }
