"""GCP Firewall Atomic Configuration"""
from dataclasses import dataclass
from typing import Any, Dict, Optional, List

@dataclass
class GCPFirewallAtomicConfig:
    network_id: str
    firewall_name: str
    project_name: str
    environment: str
    allows: List[Dict[str, Any]]
    source_ranges: List[str]
    project: Optional[str] = None
    description: Optional[str] = None
    
    def __init__(self, config: Dict[str, Any]):
        self.network_id = config.get('networkId')
        self.project_name = config.get('projectName', 'my-project')
        self.environment = config.get('environment', 'dev')
        self.project = config.get('project')
        self.firewall_name = config.get('firewallName', f"{self.project_name}-{self.environment}-fw")
        self.allows = config.get('allows', [])
        self.source_ranges = config.get('sourceRanges', ['0.0.0.0/0'])
        self.description = config.get('description')
        
        if not self.network_id:
            raise ValueError("networkId is required")
