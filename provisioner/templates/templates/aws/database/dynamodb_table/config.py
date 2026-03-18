"""
Configuration parser for DynamoDB Table template
"""
from typing import Dict, Any, List, Optional


class DynamoDBTableConfig:
    def __init__(self, raw_config: Dict[str, Any]):
        """Parse configuration from user input"""
        self.raw_config = raw_config
        self.parameters = raw_config.get('parameters', {}).get('aws', {})

        # Metadata
        self.environment = raw_config.get('environment', 'dev')
        self.region = raw_config.get('region', 'us-east-1')
        self.project_name = (
            self.parameters.get('project_name') or 
            self.parameters.get('projectName') or
            raw_config.get('project_name') or 
            raw_config.get('projectName') or 
            'archie-db'
        )

        # Core settings
        self.table_name = self.parameters.get('table_name') or self.parameters.get('tableName') or f"{self.project_name}-{self.environment}-table"
        self.hash_key = self.parameters.get('hash_key') or self.parameters.get('hashKey', 'id')
        self.range_key = self.parameters.get('range_key') or self.parameters.get('rangeKey')

        # Attribute definitions: list of {name, type}
        self.attributes: List[Dict[str, Any]] = self.parameters.get('attributes') or self.parameters.get('attribute_definitions', [])
        
        # If attributes not provided, build from keys
        if not self.attributes:
            self.attributes = [{"name": self.hash_key, "type": self.parameters.get("hash_key_type", "S")}]
            if self.range_key:
                self.attributes.append({"name": self.range_key, "type": self.parameters.get("range_key_type", "S")})
        # Billing
        self.billing_mode = self.parameters.get('billing_mode') or self.parameters.get('billingMode', 'PAY_PER_REQUEST')
        self.read_capacity = int(self.parameters.get('read_capacity')) if self.parameters.get('read_capacity') else (int(self.parameters.get('readCapacity')) if self.parameters.get('readCapacity') else None)
        self.write_capacity = int(self.parameters.get('write_capacity')) if self.parameters.get('write_capacity') else (int(self.parameters.get('writeCapacity')) if self.parameters.get('writeCapacity') else None)

        # Features
        self.global_secondary_indexes = self.parameters.get('global_secondary_indexes') or self.parameters.get('globalSecondaryIndexes', [])
        self.server_side_encryption = self.parameters.get('server_side_encryption') or self.parameters.get('serverSideEncryption')
        self.ttl = self.parameters.get('ttl')

        # Tags
        self.tags = raw_config.get('tags', {})

        # Collect any extra args passed through
        excluded_keys = [
            'table_name', 'tableName', 'project_name', 'projectName', 'environment', 'region',
            'attributes', 'hash_key', 'hashKey', 'range_key', 'rangeKey',
            'billing_mode', 'billingMode', 'read_capacity', 'readCapacity',
            'write_capacity', 'writeCapacity', 'global_secondary_indexes',
            'globalSecondaryIndexes', 'server_side_encryption', 'serverSideEncryption', 'ttl',
            'tags', 'cloud',
        ]
        self.extra_args = {k: v for k, v in self.parameters.items() if k not in excluded_keys}

        self._validate()

    def _validate(self):
        if not self.table_name:
            raise ValueError('tableName is required')
        if not self.attributes or not isinstance(self.attributes, list):
            raise ValueError('attributes (list) is required')

    @staticmethod
    def get_config_schema() -> Dict[str, Any]:
        """Get JSON schema for UI configuration."""
        return {
            "type": "object",
            "properties": {
                "essentials_header": {
                    "type": "separator",
                    "title": "Template Essentials",
                    "group": "Essentials",
                    "isEssential": True,
                    "order": 0
                },
                "project_name": {
                    "type": "string",
                    "title": "Project Name",
                    "description": "Unique name for this deployment (lowercase, no spaces)",
                    "default": "archie-db",
                    "group": "Essentials",
                    "isEssential": True,
                    "order": 1
                },
                "region": {
                    "type": "string",
                    "title": "AWS Region",
                    "description": "Region to deploy the table",
                    "default": "us-east-1",
                    "group": "Essentials",
                    "isEssential": True,
                    "order": 2
                },
                "table_header": {
                    "type": "separator",
                    "title": "Table Settings",
                    "group": "Table Settings",
                    "isEssential": True,
                    "order": 10
                },
                "tableName": {
                    "type": "string",
                    "title": "Table Name",
                    "description": "Name of the DynamoDB table",
                    "group": "Table Settings",
                    "isEssential": True,
                    "order": 11
                },
                "hashKey": {
                    "type": "string",
                    "title": "Partition Key (Hash Key)",
                    "description": "Primary key attribute name",
                    "default": "id",
                    "group": "Table Settings",
                    "isEssential": True,
                    "order": 12
                },
                "rangeKey": {
                    "type": "string",
                    "title": "Sort Key (Range Key)",
                    "description": "Optional sort key attribute name",
                    "group": "Table Settings",
                    "order": 13
                },
                "billingMode": {
                    "type": "string",
                    "title": "Billing Mode",
                    "description": "Capacity billing model",
                    "default": "PAY_PER_REQUEST",
                    "enum": ["PAY_PER_REQUEST", "PROVISIONED"],
                    "group": "Table Settings",
                    "isEssential": True,
                    "order": 14
                },
                "readCapacity": {
                    "type": "number",
                    "title": "Read Capacity Units",
                    "description": "Provisioned read throughput (only if billing mode is PROVISIONED)",
                    "default": 5,
                    "group": "Table Settings",
                    "order": 15
                },
                "writeCapacity": {
                    "type": "number",
                    "title": "Write Capacity Units",
                    "description": "Provisioned write throughput (only if billing mode is PROVISIONED)",
                    "default": 5,
                    "group": "Table Settings",
                    "order": 16
                }
            },
            "required": ["project_name", "region", "tableName", "hashKey"]
        }
