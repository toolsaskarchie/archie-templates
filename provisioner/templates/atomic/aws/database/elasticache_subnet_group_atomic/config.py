"""AWS ElastiCache Subnet Group Atomic Configuration"""
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

@dataclass
class ElastiCacheSubnetGroupAtomicConfig:
    name: str
    subnet_ids: List[str]
    project_name: str
    environment: str
    region: str
    description: Optional[str] = None
    tags: Optional[Dict[str, str]] = None
    
    def __init__(self, config: Dict[str, Any]):
        aws_params = config.get('parameters', {}).get('aws', {})
        self.project_name = aws_params.get('project_name', 'my-project')
        self.environment = aws_params.get('environment', 'dev')
        self.region = aws_params.get('region', 'us-east-1')
        self.name = aws_params.get('name', f"{self.project_name}-{self.environment}-cache-subnet-group")
        self.subnet_ids = aws_params.get('subnet_ids', [])
        self.description = aws_params.get('description', f'ElastiCache subnet group for {self.project_name}')
        self.tags = aws_params.get('tags', {})
        
        # Collect all extra kwargs for the component
        self.extra_args = {k: v for k, v in aws_params.items() if k not in [
            'project_name', 'environment', 'region', 'name', 'subnet_ids',
            'description', 'tags'
        ]}
        
        if not self.subnet_ids:
            raise ValueError("subnet_ids is required for ElastiCache Subnet Group")
