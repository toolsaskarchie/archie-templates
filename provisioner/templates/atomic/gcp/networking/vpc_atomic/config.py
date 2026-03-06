"""GCP VPC Atomic Configuration"""
from dataclasses import dataclass
from typing import Any, Dict, Optional

@dataclass
class GCPVPCAtomicConfig:
    """Configuration for atomic GCP VPC"""
    project: str
    region: str
    environment: str
    project_name: str
    vpc_name: str
    auto_create_subnetworks: bool = False
    routing_mode: str = "REGIONAL"
    description: Optional[str] = None
    
    def __init__(self, config: Dict[str, Any]):
        self.project = config.get('project')
        self.region = config.get('region', 'us-central1')
        self.environment = config.get('environment', 'dev')
        self.project_name = config.get('projectName', 'my-project')
        
        self.vpc_name = config.get('vpcName', f"{self.project_name}-{self.environment}-vpc")
        self.auto_create_subnetworks = config.get('autoCreateSubnetworks', False)
        self.routing_mode = config.get('routingMode', 'REGIONAL')
        self.description = config.get('description')
        
        if not self.project:
            raise ValueError("project is required")
