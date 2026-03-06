"""AWS Route Table Atomic Configuration"""
from dataclasses import dataclass
from typing import Any, Dict, Optional

@dataclass
class RouteTableAtomicConfig:
    vpc_id: str
    route_table_name: str
    project_name: str
    environment: str
    
    def __init__(self, config: Dict[str, Any]):
        aws_params = config.get('parameters', {}).get('aws', {})
        self.vpc_id = aws_params.get('vpc_id')
        self.project_name = aws_params.get('project_name', 'my-project')
        self.environment = aws_params.get('environment', 'dev')
        self.route_table_name = aws_params.get('route_table_name', f"{self.project_name}-{self.environment}-rt")
        
        if not self.vpc_id:
            raise ValueError("vpc_id is required")
