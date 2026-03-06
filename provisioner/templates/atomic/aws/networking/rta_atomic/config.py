"""AWS Route Table Association Atomic Configuration"""
from dataclasses import dataclass
from typing import Any, Dict, Optional

@dataclass
class RTAAtomicConfig:
    route_table_id: str
    subnet_id: Optional[str] = None
    gateway_id: Optional[str] = None
    
    def __init__(self, config: Dict[str, Any]):
        aws_params = config.get('parameters', {}).get('aws', {})
        self.route_table_id = aws_params.get('route_table_id')
        self.subnet_id = aws_params.get('subnet_id')
        self.gateway_id = aws_params.get('gateway_id')
        
        if not self.route_table_id:
            raise ValueError("route_table_id is required")
        if not self.subnet_id and not self.gateway_id:
            raise ValueError("Either subnet_id or gateway_id is required")
