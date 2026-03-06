"""AWS RDS Instance Atomic Configuration"""
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import pulumi

@dataclass
class RDSInstanceAtomicConfig:
    identifier: str
    engine: str
    engine_version: str
    instance_class: str
    allocated_storage: int
    username: str
    password: Any  # Usually pulumi.Output
    project_name: str
    environment: str
    region: str
    db_subnet_group_name: Optional[str] = None
    vpc_security_group_ids: Optional[List[str]] = None
    
    def __init__(self, config: Dict[str, Any]):
        aws_params = config.get('parameters', {}).get('aws', {})
        self.project_name = aws_params.get('project_name', 'my-project')
        self.environment = aws_params.get('environment', 'dev')
        self.region = aws_params.get('region', 'us-east-1')
        self.identifier = aws_params.get('identifier', f"{self.project_name}-{self.environment}-db")
        self.engine = aws_params.get('engine', 'postgres')
        self.engine_version = aws_params.get('engine_version', '15.4')
        self.instance_class = aws_params.get('instance_class', 'db.t3.micro')
        self.allocated_storage = aws_params.get('allocated_storage', 20)
        self.username = aws_params.get('username', 'dbadmin')
        self.password = aws_params.get('password')
        self.db_subnet_group_name = aws_params.get('db_subnet_group_name')
        self.vpc_security_group_ids = aws_params.get('vpc_security_group_ids')
        
        # Collect all extra kwargs for the component
        self.extra_args = {k: v for k, v in aws_params.items() if k not in [
            'project_name', 'environment', 'region', 'identifier', 'engine', 
            'engine_version', 'instance_class', 'allocated_storage', 'username', 
            'password', 'db_subnet_group_name', 'vpc_security_group_ids'
        ]}
        
        if not self.password:
            raise ValueError("password is required for RDS Instance")
