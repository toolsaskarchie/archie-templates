"""AWS NAT Gateway Atomic Configuration"""
from dataclasses import dataclass
from typing import Any, Dict, Optional

@dataclass
class NATGatewayAtomicConfig:
    subnet_id: str
    allocation_id: str
    nat_name: str
    project_name: str
    environment: str
    
    def __init__(self, config: Dict[str, Any]):
        aws_params = config.get('parameters', {}).get('aws', {})
        self.subnet_id = aws_params.get('subnet_id')
        self.allocation_id = aws_params.get('allocation_id')
        self.project_name = aws_params.get('project_name', 'my-project')
        self.environment = aws_params.get('environment', 'dev')
        self.nat_name = aws_params.get('nat_name', f"{self.project_name}-{self.environment}-nat")
        
        if not self.subnet_id:
            raise ValueError("subnet_id is required")
        if not self.allocation_id:
            raise ValueError("allocation_id is required")
