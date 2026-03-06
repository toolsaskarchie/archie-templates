"""
AWS DynamoDB Table Template
Creates a standalone AWS DynamoDB Table using the DynamoDBTableComponent.
"""
from typing import Any, Dict, Optional
import pulumi

from provisioner.templates.base import template_registry, InfrastructureTemplate
import pulumi_aws as aws
from .config import DynamoDBAtomicConfig
from provisioner.utils.aws import get_standard_tags


@template_registry("aws-dynamodb-atomic")
class DynamoDBAtomicTemplate(InfrastructureTemplate):
    """
    AWS DynamoDB Table Template
    """

    def __init__(self, name: str = None, config: Dict[str, Any] = None, **kwargs):
        raw_config = config or kwargs or {}
        self.cfg = DynamoDBAtomicConfig(raw_config)

        if name is None:
            name = self.cfg.table_name

        super().__init__(name, raw_config)
        self.table: Optional[aws.dynamodb.Table] = None

    def create_infrastructure(self) -> Dict[str, Any]:
        """Create DynamoDB Table using DynamoDBTableComponent"""
        tags = get_standard_tags(
            project=self.cfg.project_name,
            environment=self.cfg.environment,
            template="dynamodb-atomic"
        )
        
        # Merge metadata tags (department, owner, etc.)
        tags.update(self.cfg.metadata_tags)

        self.table = aws.dynamodb.Table(
            self.name,
            name=self.cfg.table_name,
            attributes=self.cfg.attributes,
            hash_key=self.cfg.hash_key,
            range_key=self.cfg.range_key,
            billing_mode=self.cfg.billing_mode,
            read_capacity=self.cfg.read_capacity,
            write_capacity=self.cfg.write_capacity,
            tags={**tags, "Name": self.cfg.table_name},
            **self.cfg.extra_args
        )

        pulumi.export("table_name", self.table.name)
        pulumi.export("table_arn", self.table.arn)

        return self.get_outputs()

    def get_outputs(self) -> Dict[str, Any]:
        if not self.table:
            return {}
        return {
            "table_name": self.table.name,
            "table_arn": self.table.arn,
            "table_id": self.table.id,
        }

    @classmethod
    def get_metadata(cls):
        return {
            "name": "dynamodb-atomic",
            "title": "DynamoDB Table",
            "description": "Standalone AWS DynamoDB Table resource.",
            "category": "database",
            "provider": "aws",
            "tier": "atomic"
        }
