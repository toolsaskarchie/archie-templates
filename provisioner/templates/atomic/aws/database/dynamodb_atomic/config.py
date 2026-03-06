"""AWS DynamoDB Atomic Configuration"""
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class DynamoDBAtomicConfig:
    table_name: str
    attributes: List[Dict[str, Any]]
    hash_key: str
    range_key: Optional[str]
    billing_mode: Optional[str]
    read_capacity: Optional[int]
    write_capacity: Optional[int]
    project_name: str
    environment: str
    region: str

    def __init__(self, config: Dict[str, Any]):
        aws_params = config.get('parameters', {}).get('aws', {})
        self.project_name = aws_params.get('project_name', 'my-project')
        self.environment = aws_params.get('environment', 'dev')
        self.region = aws_params.get('region', 'us-east-1')
        self.table_name = aws_params.get('table_name', aws_params.get('tableName', f"{self.project_name}-{self.environment}-table"))
        self.attributes = aws_params.get('attributes', aws_params.get('attribute_definitions', []))
        self.hash_key = aws_params.get('hash_key', aws_params.get('hashKey', 'id'))
        self.range_key = aws_params.get('range_key', aws_params.get('rangeKey'))
        self.billing_mode = aws_params.get('billing_mode', aws_params.get('billingMode', 'PAY_PER_REQUEST'))
        self.read_capacity = aws_params.get('read_capacity', aws_params.get('readCapacity'))
        self.write_capacity = aws_params.get('write_capacity', aws_params.get('writeCapacity'))

        # Collect all extra kwargs for the component
        # Exclude common metadata fields that should be in tags, not Table args
        self.extra_args = {k: v for k, v in aws_params.items() if k not in [
            'project_name', 'environment', 'region', 'table_name', 'attributes',
            'hash_key', 'range_key', 'billing_mode', 'read_capacity', 'write_capacity',
            'tableName', 'hashKey', 'rangeKey', 'billingMode', 'readCapacity', 'writeCapacity',
            'attribute_definitions',  # Alternative naming
            # Common metadata fields (should be in tags, not constructor args)
            'department', 'owner', 'cost_center', 'team', 'application', 'service',
            'business_unit', 'managed_by', 'created_by', 'cost_centre'
        ]}

        # Extract metadata fields for tagging
        metadata_fields = ['department', 'owner', 'cost_center', 'team', 'application', 
                          'service', 'business_unit', 'created_by', 'cost_centre']
        self.metadata_tags = {
            k.replace('_', '-').title(): v 
            for k, v in aws_params.items() 
            if k in metadata_fields and v
        }

        if not self.attributes:
            raise ValueError("attributes is required for DynamoDB Atomic template")
