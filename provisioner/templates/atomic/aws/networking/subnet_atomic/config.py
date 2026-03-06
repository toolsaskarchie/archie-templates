"""AWS Subnet Atomic Configuration"""
from dataclasses import dataclass
from typing import Any, Dict, Optional

@dataclass
class SubnetAtomicConfig:
    vpc_id: str
    cidr_block: str
    az: str
    subnet_name: str
    project_name: str
    environment: str
    map_public_ip_on_launch: bool = False
    
    def __init__(self, config: Dict[str, Any]):
        aws_params = config.get('parameters', {}).get('aws', {})
        self.vpc_id = aws_params.get('vpc_id')
        self.cidr_block = aws_params.get('cidr_block')
        self.availability_zone= aws_params.get('az')
        self.project_name = aws_params.get('project_name', 'my-project')
        self.environment = aws_params.get('environment', 'dev')
        self.subnet_name = aws_params.get('subnet_name', f"{self.project_name}-{self.environment}-subnet")
        self.map_public_ip_on_launch = aws_params.get('map_public_ip_on_launch', False)
        
        if not self.vpc_id:
            raise ValueError("vpc_id is required")
        if not self.cidr_block:
            raise ValueError("cidr_block is required")
        if not self.availability_zone:
            raise ValueError("az is required")
