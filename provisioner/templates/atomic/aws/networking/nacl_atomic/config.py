"""AWS NACL Atomic Configuration"""
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

@dataclass
class NACLAtomicConfig:
    vpc_id: str
    subnet_ids: List[str]
    ingress: List[Dict]
    egress: List[Dict]
    project_name: str
    environment: str
    nacl_name: str
    
    def __init__(self, config: Dict[str, Any]):
        aws_params = config.get('parameters', {}).get('aws', {})
        self.vpc_id = aws_params.get('vpc_id')
        self.subnet_ids = aws_params.get('subnet_ids', [])
        self.ingress = aws_params.get('ingress', [])
        self.egress = aws_params.get('egress', [])
        self.project_name = aws_params.get('project_name', 'my-project')
        self.environment = aws_params.get('environment', 'dev')
        self.nacl_name = aws_params.get('nacl_name', f"{self.project_name}-{self.environment}-nacl")
        
        if not self.vpc_id:
            raise ValueError("vpc_id is required for NACL Atomic")
