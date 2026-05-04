"""
Redis Non-Prod Template

Deploys a managed Redis cluster using AWS ElastiCache for development and testing:
- ElastiCache Redis cluster (single-node or multi-node)
- ElastiCache subnet group for VPC placement
- Security group with Redis port access
- Automatic backups and maintenance windows
- Optional Multi-AZ for high availability

Features:
- Cost-optimized for non-production workloads
- Configurable node type and count
- Automatic backups with retention
- Security group with configurable CIDR access
- Multi-AZ support for testing HA scenarios

Architecture: Uses ElastiCacheClusterAtomicTemplate, ElastiCacheSubnetGroupAtomicTemplate, SecurityGroupAtomicTemplate
"""
from typing import Any, Dict, Optional
import pulumi
import pulumi_aws as aws

# Import Archie utils for consistent patterns
from provisioner.utils.aws import (
    ResourceNamer,
    get_standard_tags
)
from provisioner.templates.base import template_registry, InfrastructureTemplate
from provisioner.templates.templates.aws.elasticache.redis_nonprod.config import RedisNonProdConfig
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory


@template_registry("aws-redis-nonprod")
class RedisNonProdTemplate(InfrastructureTemplate):
    """
    Redis Non-Prod Template - Pattern B Implementation
    
    Creates:
    - EC2 Security Group for Redis access
    - ElastiCache Subnet Group
    - ElastiCache Redis Cluster
    """

    def __init__(self, name: str = None, config: Dict[str, Any] = None, **kwargs):
        """Initialize Redis template"""
        raw_config = config or kwargs or {}
        self.cfg = RedisNonProdConfig(raw_config)

        if name is None:
            name = raw_config.get('cluster_name', 'redis-nonprod')

        super().__init__(name, raw_config)

        # Initialize resources
        self.security_group: Optional[aws.ec2.SecurityGroup] = None
        self.subnet_group: Optional[aws.elasticache.SubnetGroup] = None
        self.cluster: Optional[aws.elasticache.Cluster] = None

    def _cfg(self, key: str, default=None):
        """Read config from root, parameters.aws, or parameters (Rule #6)"""
        params = self.config.get('parameters', {})
        aws_params = params.get('aws', {}) if isinstance(params, dict) else {}
        return (
            self.config.get(key) or
            (aws_params.get(key) if isinstance(aws_params, dict) else None) or
            (params.get(key) if isinstance(params, dict) else None) or
            default
        )

    def create_infrastructure(self) -> Dict[str, Any]:
        """Deploy infrastructure (implements abstract method)"""
        return self.create()

    def create(self) -> Dict[str, Any]:
        """Deploy Redis infrastructure using factory pattern"""
        
        # Initialize namer
        environment = self.cfg.environment or 'nonprod'
        namer = ResourceNamer(
            project=self.cfg.project,
            environment=environment,
            region=self.cfg.region,
            template="aws-redis-nonprod"
        )

        cluster_name = self.cfg.cluster_name

        # Tags
        tags = get_standard_tags(
            project=self.cfg.project,
            environment=environment,
            template="aws-redis-nonprod"
        )
        tags.update(self.cfg.resource_tags)

        # 1. SECURITY GROUP
        sg_name = (self.config.get('redis_sg_name') or self.config.get('parameters', {}).get('redis_sg_name')) or f"{self.name}-sg"
        self.security_group = factory.create(
            "aws:ec2:SecurityGroup",
            sg_name,
            description=f'Security group for {cluster_name} Redis cluster',
            vpc_id=self.cfg.vpc_id,
            ingress=[
                {
                    'description': 'Redis access',
                    'from_port': self.cfg.port,
                    'to_port': self.cfg.port,
                    'protocol': 'tcp',
                    'cidr_blocks': self.cfg.allowed_cidr_blocks
                }
            ],
            egress=[
                {
                    'description': 'Allow all outbound',
                    'from_port': 0,
                    'to_port': 0,
                    'protocol': '-1',
                    'cidr_blocks': ['0.0.0.0/0']
                }
            ],
            tags=tags
        )

        # 2. SUBNET GROUP
        subnet_group_name = (self.config.get('redis_subnet_group_name') or self.config.get('parameters', {}).get('redis_subnet_group_name')) or f"{self.name}-subnet-group"
        self.subnet_group = factory.create(
            "aws:elasticache:SubnetGroup",
            subnet_group_name,
            description=f'Subnet group for {cluster_name} Redis cluster',
            subnet_ids=self.cfg.subnet_ids,
            tags=tags
        )

        # 3. REDIS CLUSTER
        redis_cluster_name = (self.config.get('redis_cluster_resource_name') or self.config.get('parameters', {}).get('redis_cluster_resource_name')) or f"{self.name}-cluster"
        self.cluster = factory.create(
            "aws:elasticache:Cluster",
            redis_cluster_name,
            cluster_id=cluster_name,
            engine='redis',
            engine_version=self.cfg.engine_version,
            node_type=self.cfg.node_type,
            num_cache_nodes=self.cfg.num_cache_nodes,
            port=self.cfg.port,
            subnet_group_name=self.subnet_group.name,
            security_group_ids=[self.security_group.id],
            az_mode=self.cfg.az_mode,
            snapshot_retention_limit=self.cfg.snapshot_retention_limit,
            snapshot_window=self.cfg.snapshot_window,
            maintenance_window=self.cfg.maintenance_window,
            tags=tags
        )

        # Output logic
        connection_string = pulumi.Output.concat(self.cluster.cache_nodes[0].address, ":", str(self.cfg.port))

        pulumi.export('cluster_id', self.cluster.cluster_id)
        pulumi.export('endpoint', self.cluster.cache_nodes[0].address)
        pulumi.export('port', self.cfg.port)
        pulumi.export('connection_string', connection_string)
        pulumi.export('redis_sg_name', sg_name)
        pulumi.export('redis_subnet_group_name', subnet_group_name)
        pulumi.export('redis_cluster_resource_name', redis_cluster_name)

        return self.get_outputs()

    def get_outputs(self) -> Dict[str, Any]:
        """Get infrastructure outputs"""
        if not self.cluster:
            return {}
        
        # Note: In non-prod (single node), we use cache_nodes[0]. In cluster mode, we'd use configuration_endpoint_address
        endpoint = self.cluster.cache_nodes[0].address
        
        return {
            'cluster_id': self.cluster.cluster_id,
            'cluster_arn': self.cluster.arn,
            'endpoint': endpoint,
            'port': self.cfg.port,
            'connection_string': pulumi.Output.concat(endpoint, ":", str(self.cfg.port)),
            'security_group_id': self.security_group.id if self.security_group else None,
            'subnet_group_name': self.subnet_group.name if self.subnet_group else None,
            'engine_version': self.cfg.engine_version,
            'node_type': self.cfg.node_type,
            'num_nodes': self.cfg.num_cache_nodes,
            'multi_az': self.cfg.multi_az_enabled
        }

    @classmethod
    def get_metadata(cls) -> Dict[str, Any]:
        """Pattern B Metadata source of truth"""
        return {
            "name": "aws-redis-nonprod",
            "title": "ElastiCache Redis",
            "description": "Managed Redis cluster for development and testing with cost-optimized nodes and automated snapshots.",
            "category": "database",
            "version": "1.0.0",
            "author": "InnovativeApps",
            "cloud": "aws",
            "environment": "nonprod",
            "base_cost": "$15/month",
            "features": [
                "High-performance managed Redis engine",
                "Cost-optimized burstable node types (t3 family)",
                "Integrated security group with Redis port isolation",
                "Automated backups and maintenance windows",
                "Multi-AZ support for testing HA failover"
            ],
            "tags": ["redis", "elasticache", "database", "cache", "nonprod"],
            "deployment_time": "5-10 minutes",
            "complexity": "intermediate",
            "use_cases": [
                "Application session caching",
                "API response caching",
                "Pub/Sub messaging for microservices",
                "Rate limiting and throttling",
                "Development and testing cache layer",
            ],
            "pillars": [
                {
                    "title": "Performance Efficiency",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "In-memory data store delivering sub-millisecond latency for caching and session management",
                    "practices": [
                        "In-memory architecture delivers sub-millisecond read/write latency",
                        "Configurable node types from cache.t3.micro to cache.r6g for workload matching",
                        "Redis data structures (sorted sets, hashes) optimize application-level operations",
                        "Multi-node clusters distribute load across cache nodes",
                        "Dedicated subnet group ensures low-latency VPC placement"
                    ]
                },
                {
                    "title": "Security",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "VPC isolation with dedicated security groups and encryption options",
                    "practices": [
                        "Dedicated security group restricts access to Redis port only",
                        "VPC subnet group ensures cluster runs in private network",
                        "Encryption at rest available with AWS-managed keys",
                        "Encryption in transit available for client connections",
                        "Configurable CIDR-based access control for ingress rules"
                    ]
                },
                {
                    "title": "Reliability",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Automated snapshots and optional Multi-AZ for high availability testing",
                    "practices": [
                        "Automated daily snapshots with configurable retention period",
                        "Multi-AZ replication available for failover testing",
                        "Automatic node replacement on hardware failure",
                        "Configurable maintenance windows for controlled patching",
                        "Snapshot-based restore for rapid recovery scenarios"
                    ]
                },
                {
                    "title": "Operational Excellence",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Managed service with automated maintenance and monitoring integration",
                    "practices": [
                        "Infrastructure as Code with Pulumi for repeatable deployments",
                        "CloudWatch metrics for cache hit ratio, memory, and CPU monitoring",
                        "Automated maintenance windows for engine patching",
                        "Configurable snapshot windows for backup scheduling",
                        "Standard tagging for resource identification and cost tracking"
                    ]
                },
                {
                    "title": "Cost Optimization",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Burstable node types and right-sizing options minimize nonprod costs",
                    "practices": [
                        "Burstable cache.t3 nodes for variable development workloads",
                        "Single-node default eliminates replication costs for nonprod",
                        "Reserved node pricing available for predictable usage",
                        "Right-sizing from micro to xlarge based on cache requirements",
                        "No storage costs beyond node memory allocation"
                    ]
                },
                {
                    "title": "Sustainability",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Efficient in-memory service with right-sized nodes and managed infrastructure",
                    "practices": [
                        "Graviton-based cache.r6g nodes available for energy efficiency",
                        "Burstable instances match resource usage to actual demand",
                        "In-memory architecture eliminates disk I/O overhead",
                        "Managed service reduces idle infrastructure waste",
                        "Regional deployment minimizes data transfer distances"
                    ]
                }
            ]
        }

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        """Get configuration schema for the UI"""
        schema = {
            "type": "object",
            "required": ["project_name", "cluster_name"],
            "properties": {
                "project_name": {
                    "type": "string", "title": "Project Name",
                    "description": "Unique name for this deployment",
                    "group": "Essentials", "isEssential": True, "order": 1,
                },
                "region": {
                    "type": "string", "title": "AWS Region", "default": "us-east-1",
                    "group": "Essentials", "isEssential": True, "order": 2,
                },
                "vpc_id": {
                    "type": "string", "title": "VPC ID",
                    "description": "VPC for the Redis cluster",
                    "group": "Networking", "order": 10,
                },
                "subnet_ids": {
                    "type": "array", "title": "Subnet IDs",
                    "description": "Subnets for the ElastiCache subnet group",
                    "group": "Networking", "order": 11,
                },
            }
        }
        
        # Add Template specific fields
        schema["properties"].update({
            "cluster_name": {
                "type": "string",
                "title": "Cluster Name",
                "description": "Name for the Redis cluster",
                "default": "redis-nonprod",
                "pattern": "^[a-zA-Z][a-zA-Z0-9-]{0,39}$",
                "group": "Redis Settings"
            },
            "engine_version": {
                "type": "string",
                "title": "Engine Version",
                "description": "Redis version",
                "default": "7.0",
                "group": "Redis Settings"
            },
            "node_type": {
                "type": "string",
                "title": "Node Type",
                "description": "Cache node instance type",
                "default": "cache.t3.micro",
                "group": "Redis Settings"
            },
            "num_cache_nodes": {
                "type": "number",
                "title": "Number of Nodes",
                "description": "Number of cache nodes in the cluster",
                "default": 1,
                "minimum": 1,
                "group": "Redis Settings"
            },
            "port": {
                "type": "number",
                "title": "Port",
                "description": "Redis connection port",
                "default": 6379,
                "group": "Network Settings"
            },
            "team_name": {
                "type": "string",
                "default": "",
                "title": "Team Name",
                "description": "Team that owns this resource",
                "order": 50,
                "group": "Tags",
            },
        })

        return schema
