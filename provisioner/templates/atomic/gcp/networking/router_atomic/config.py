"""GCP Router Atomic Configuration"""
from dataclasses import dataclass
from typing import Any, Dict, Optional

@dataclass
class GCPRouterAtomicConfig:
    network_id: str
    region: str
    router_name: str
    project_name: str
    environment: str
    project: Optional[str] = None
    
    def __init__(self, config: Dict[str, Any]):
        self.network_id = config.get('networkId')
        self.region = config.get('region', 'us-central1')
        self.project_name = config.get('projectName', 'my-project')
        self.environment = config.get('environment', 'dev')
        self.project = config.get('project')
        self.router_name = config.get('routerName', f"{self.project_name}-{self.environment}-router")
        
        if not self.network_id:
            raise ValueError("networkId is required")
