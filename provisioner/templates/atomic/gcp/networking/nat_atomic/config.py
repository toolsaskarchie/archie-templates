"""GCP NAT Atomic Configuration"""
from dataclasses import dataclass
from typing import Any, Dict, Optional

@dataclass
class GCPNATAtomicConfig:
    router_name: str
    region: str
    nat_name: str
    project_name: str
    environment: str
    project: Optional[str] = None
    nat_ip_allocate_option: str = "AUTO_ONLY"
    source_subnetwork_ip_ranges_to_nat: str = "ALL_SUBNETWORKS_ALL_IP_RANGES"
    
    def __init__(self, config: Dict[str, Any]):
        self.router_name = config.get('routerName')
        self.region = config.get('region', 'us-central1')
        self.project_name = config.get('projectName', 'my-project')
        self.environment = config.get('environment', 'dev')
        self.project = config.get('project')
        self.nat_name = config.get('natName', f"{self.project_name}-{self.environment}-nat")
        self.nat_ip_allocate_option = config.get('natIpAllocateOption', "AUTO_ONLY")
        self.source_subnetwork_ip_ranges_to_nat = config.get('sourceSubnetworkIpRangesToNat', "ALL_SUBNETWORKS_ALL_IP_RANGES")
        
        if not self.router_name:
            raise ValueError("routerName is required")
