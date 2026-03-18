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
        self.security_group = factory.create(
            "aws:ec2:SecurityGroup",
            f"{self.name}-sg",
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
        self.subnet_group = factory.create(
            "aws:elasticache:SubnetGroup",
            f"{self.name}-subnet-group",
            description=f'Subnet group for {cluster_name} Redis cluster',
            subnet_ids=self.cfg.subnet_ids,
            tags=tags
        )

        # 3. REDIS CLUSTER
        self.cluster = factory.create(
            "aws:elasticache:Cluster",
            f"{self.name}-cluster",
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
    def get_metadata(cls):
        """Template metadata for marketplace registration"""
        from provisioner.templates.base.template import TemplateMetadata, TemplateCategory
        return TemplateMetadata(
            name="aws-redis-nonprod",
            title="Distributed Cache (Redis)",
            description="Rapidly deploy a managed Redis cluster for development and testing using AWS ElastiCache. Features cost-optimized t3-family nodes, automated snapshot integration, and pre-configured security group isolation. Perfect for application caching and session management.",
            category=TemplateCategory.DATABASE,
            version="1.0.0",
            author="InnovativeApps",
            supported_regions=["us-east-1", "us-east-2", "us-west-2"],
            is_listed_in_marketplace=True,
            marketplace_group="aws-caching-group",
            tags=["redis", "elasticache", "database", "cache", "nonprod"],
            features=[
                "High-Performance Managed Redis Engine",
                "Cost-Optimized Burstable Node Types (t3 family)",
                "Integrated Security Group with Redis Port isolation",
                "Automated Backups & Maintenance Windows",
                "Multi-AZ Support for testing HA failover",
                "Intelligent Subnet Group placement for VPCs"
            ],
            estimated_cost="$12-35/month (depends on node type)",
            complexity="medium",
            deployment_time="5-10 minutes"
        )

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        """Get configuration schema for the UI"""
        schema = {
            "type": "object",
            "required": ["project_name", "cluster_name"],
            "properties": {}
        }
        
        # Add Project/Env fields
        schema["properties"].update(get_project_env_schema())
        
        # Add VPC fields
        schema["properties"].update(get_vpc_selection_schema())
        
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
            }
        })
        
        return schema
