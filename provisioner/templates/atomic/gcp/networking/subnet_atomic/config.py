"""GCP Subnet Atomic Configuration"""
from dataclasses import dataclass
from typing import Any, Dict, Optional

@dataclass
class GCPSubnetAtomicConfig:
    network_id: str
    ip_cidr_range: str
    region: str
    subnet_name: str
    project_name: str
    environment: str
    project: Optional[str] = None
    private_ip_google_access: bool = True
    description: Optional[str] = None
    
    def __init__(self, config: Dict[str, Any]):
        self.network_id = config.get('networkId')
        self.ip_cidr_range = config.get('ipCidrRange')
        self.region = config.get('region', 'us-central1')
        self.project_name = config.get('projectName', 'my-project')
        self.environment = config.get('environment', 'dev')
        self.project = config.get('project')
        self.subnet_name = config.get('subnetName', f"{self.project_name}-{self.environment}-subnet")
        self.private_ip_google_access = config.get('privateIpGoogleAccess', True)
        self.description = config.get('description')
        
        if not self.network_id:
            raise ValueError("networkId is required")
        if not self.ip_cidr_range:
            raise ValueError("ipCidrRange is required")
