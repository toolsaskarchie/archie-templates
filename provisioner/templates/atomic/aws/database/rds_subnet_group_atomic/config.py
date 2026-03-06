"""AWS RDS Subnet Group Atomic Configuration"""
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

@dataclass
class RDSSubnetGroupAtomicConfig:
    subnet_ids: List[str]
    subnet_group_name: str
    project_name: str
    environment: str
    description: Optional[str] = None
    
    def __init__(self, config: Dict[str, Any]):
        aws_params = config.get('parameters', {}).get('aws', {})
        self.subnet_ids = aws_params.get('subnet_ids', [])
        self.project_name = aws_params.get('project_name', 'my-project')
        self.environment = aws_params.get('environment', 'dev')
        self.subnet_group_name = aws_params.get('subnet_group_name', f"{self.project_name}-{self.environment}-db-sng")
        self.description = aws_params.get('description')
        
        if not self.subnet_ids or len(self.subnet_ids) < 2:
            raise ValueError("At least 2 subnet_ids are required for RDS Subnet Group")
