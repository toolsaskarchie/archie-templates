"""AWS VPC Endpoint Atomic Configuration"""
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

@dataclass
class VPCEndpointAtomicConfig:
    vpc_id: str
    service_name: str
    project_name: str
    environment: str
    endpoint_name: str
    vpc_endpoint_type: str = "Interface"
    subnet_ids: Optional[List[str]] = None
    security_group_ids: Optional[List[str]] = None
    route_table_ids: Optional[List[str]] = None
    
    def __init__(self, config: Dict[str, Any]):
        aws_params = config.get('parameters', {}).get('aws', {})
        self.vpc_id = aws_params.get('vpc_id')
        self.service_name = aws_params.get('service_name')
        self.vpc_endpoint_type = aws_params.get('vpc_endpoint_type', 'Interface')
        self.subnet_ids = aws_params.get('subnet_ids')
        self.security_group_ids = aws_params.get('security_group_ids')
        self.route_table_ids = aws_params.get('route_table_ids')
        self.project_name = aws_params.get('project_name', 'my-project')
        self.environment = aws_params.get('environment', 'dev')
        self.endpoint_name = aws_params.get('endpoint_name', f"{self.project_name}-{self.environment}-vpce")
        
        if not self.vpc_id or not self.service_name:
            raise ValueError("vpc_id and service_name are required for VPC Endpoint Atomic")
