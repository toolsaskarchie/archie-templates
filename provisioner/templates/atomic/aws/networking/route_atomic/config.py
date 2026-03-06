"""AWS Route Atomic Configuration"""
from dataclasses import dataclass
from typing import Any, Dict, Optional

@dataclass
class RouteAtomicConfig:
    route_table_id: str
    destination_cidr_block: str
    gateway_id: Optional[str] = None
    nat_gateway_id: Optional[str] = None
    vpc_peering_connection_id: Optional[str] = None
    
    def __init__(self, config: Dict[str, Any]):
        aws_params = config.get('parameters', {}).get('aws', {})
        self.route_table_id = aws_params.get('route_table_id')
        self.destination_cidr_block = aws_params.get('destination_cidr_block', '0.0.0.0/0')
        self.gateway_id = aws_params.get('gateway_id')
        self.nat_gateway_id = aws_params.get('nat_gateway_id')
        self.vpc_peering_connection_id = aws_params.get('vpc_peering_connection_id')
        
        if not self.route_table_id:
            raise ValueError("route_table_id is required")
