"""
DynamoDB Table Template
Creates a managed DynamoDB table with optional encryption, TTL, and GSIs.

This is a Layer 3 template that uses DynamoDBAtomicTemplate.
"""
from typing import Any, Dict, Optional, List
import pulumi

# Import Archie utils for consistent patterns
from provisioner.utils.aws import (
    ResourceNamer,
    get_standard_tags
)
from provisioner.templates.base import template_registry, InfrastructureTemplate
from provisioner.templates.templates.aws.database.dynamodb_table.config import DynamoDBTableConfig
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory


@template_registry("aws-dynamodb-table")
class DynamoDBTableTemplate(InfrastructureTemplate):
    """
    DynamoDB Table Template - Pattern B Implementation
    
    Creates:
    - DynamoDB table with attributes, keys, and indexes via factory.
    """

    def __init__(self, name: str = None, config: Dict[str, Any] = None, **kwargs):
        """Initialize DynamoDB table template"""
        raw_config = config or kwargs or {}
        self.cfg = DynamoDBTableConfig(raw_config)

        if name is None:
            name = raw_config.get('tableName', 'dynamodb-table')

        super().__init__(name, raw_config)
        self.table: Optional[aws.dynamodb.Table] = None

    def create_infrastructure(self) -> Dict[str, Any]:
        """Deploy infrastructure (implements abstract method)"""
        return self.create()

    def create(self) -> Dict[str, Any]:
        """Deploy DynamoDB table using factory pattern"""
        
        # Initialize namer
        environment = self.cfg.environment or 'nonprod'
        namer = ResourceNamer(
            project=self.cfg.project_name,
            environment=environment,
            region=self.cfg.region,
            template="aws-dynamodb-table"
        )
        
        # Resolve table name
        table_name = self.cfg.table_name
        
        # Tags
        tags = get_standard_tags(
            project=self.cfg.project_name,
            environment=environment,
            template="aws-dynamodb-table"
        )
        tags.update(self.cfg.tags)
        
        # 1. Create DynamoDB Table
        self.table = factory.create(
            "aws:dynamodb:Table",
            self.name,
            name=table_name,
            attributes=self.cfg.attributes,
            hash_key=self.cfg.hash_key,
            range_key=self.cfg.range_key,
            billing_mode=self.cfg.billing_mode,
            read_capacity=self.cfg.read_capacity,
            write_capacity=self.cfg.write_capacity,
            global_secondary_indexes=self.cfg.global_secondary_indexes,
            server_side_encryption=self.cfg.server_side_encryption,
            ttl=self.cfg.ttl,
            tags=tags,
            **self.cfg.extra_args
        )

        pulumi.export("table_name", self.table.name)
        pulumi.export("table_arn", self.table.arn)

        return self.get_outputs()

    def get_outputs(self) -> Dict[str, Any]:
        """Get template outputs"""
        if not self.table:
            return {}
        
        return {
            "table_name": self.table.name,
            "table_arn": self.table.arn,
            "table_id": self.table.id,
        }

    @classmethod
    def get_metadata(cls):
        """Template metadata for marketplace registration"""
        from provisioner.templates.base.template import TemplateMetadata, TemplateCategory
        return TemplateMetadata(
            name="aws-dynamodb-table",
            title="DynamoDB Table",
            description="Highly-performant NoSQL table with automatic scaling, encrypted storage, and flexible querying via GSIs. Fully serverless database solution for modern applications.",
            category=TemplateCategory.DATABASE,
            version="1.0.0",
            author="InnovativeApps",
            tags=["dynamodb", "nosql", "database", "serverless", "aws"],
            features=[
                "Serverless On-Demand Throughput Scaling",
                "Advanced flexible schemas with attributes and GSIs",
                "Encryption at Rest with KMS management",
                "Automated TTL for efficient data lifecycle",
                "Point-in-Time Recovery enabled for durability"
            ],
            estimated_cost="$0 - $25/month (usage dependent)",
            complexity="intermediate",
            deployment_time="2-4 minutes",
            marketplace_group="DATABASES"
        )

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        """Get configuration schema for the UI"""
        return DynamoDBTableConfig.get_config_schema()
    @classmethod
    def get_diagram(cls) -> Dict[str, Any]:
        """Generate infrastructure diagram for Overview tab"""
        return {
            "title": "DynamoDB NoSQL",
            "description": "High-performance serverless key-value database",
            "layout": "hierarchical",
            "nodes": [
                {"id": "dynamodb", "type": "resource", "label": f"DynamoDB Table", "subLabel": "On-Demand/Provisioned", "style": {"highlight": True, "bgColor": "#FFF9C4", "borderColor": "#FBC02D"}},
                {"id": "indexes", "type": "group", "label": "Scaling & Querying", "style": {"borderColor": "#1976D2", "bgColor": "#E3F2FD"}, "children": [
                    {"id": "gsi", "type": "resource", "label": "Global Secondary Indexes"},
                    {"id": "ttl", "type": "resource", "label": "TTL (Auto-Cleanup)"}
                ]},
                {"id": "security", "type": "resource", "label": "Encrypted Storage", "subLabel": "AES-256 (KMS)"}
            ],
            "connections": [
                {"id": "c1", "source": "dynamodb", "target": "indexes", "label": "includes", "type": "hierarchy"},
                {"id": "c2", "source": "dynamodb", "target": "security", "label": "encrypted by", "type": "reference"}
            ]
        }

    @classmethod
    def get_template_info(cls) -> Dict[str, Any]:
        """Get template metadata for Marketplace"""
        return {
            "name": "dynamodb-table",
            "title": "DynamoDB NoSQL Table",
            "description": "A high-performance serverless NoSQL database designed for fast, granular data access.",
            "category": "database",
            "complexity": "intermediate",
            "cost_tier": "low",
            "use_cases": [
                "User sessions & profiles",
                "High-volume catalog data",
                "Serverless application state"
            ],
            "features": [
                "Serverless On-Demand Scaling",
                "Global Secondary Indexes (GSI)",
                "Native SSE Encryption",
                "Automated TTL Expiration",
                "99.99% Availability SLA"
            ],
            "estimated_cost": "$1-25/month",
            "deployment_time": "2-4 minutes",
            "required_config": ["project_name", "table_name"],
            "tags": ["dynamodb", "nosql", "aws", "serverless"],
            "outputs": [
                "table_name - The unique table identifier",
                "table_arn - Resource Name for IAM",
                "table_id - Short identifier"
            ]
        }
