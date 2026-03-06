"""AWS EIP Atomic Configuration"""
from dataclasses import dataclass
from typing import Any, Dict, Optional

@dataclass
class EIPAtomicConfig:
    eip_name: str
    project_name: str
    environment: str
    domain: str = "vpc"
    
    def __init__(self, config: Dict[str, Any]):
        aws_params = config.get('parameters', {}).get('aws', {})
        self.project_name = aws_params.get('project_name', 'my-project')
        self.environment = aws_params.get('environment', 'dev')
        self.eip_name = aws_params.get('eip_name', f"{self.project_name}-{self.environment}-eip")
        self.domain = aws_params.get('domain', 'vpc')
