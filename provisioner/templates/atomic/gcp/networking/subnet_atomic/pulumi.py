"""
GCP Subnet Template
Creates a GCP Subnetwork using the SubnetworkComponent.
"""
from typing import Any, Dict, Optional
import pulumi
import pulumi_gcp as gcp

from provisioner.templates.base import template_registry, InfrastructureTemplate
from .config import GCPSubnetAtomicConfig

@template_registry("gcp-subnet-atomic")
class GCPSubnetAtomicTemplate(InfrastructureTemplate):
    """
    GCP Subnet Template
    """
    
    def __init__(self, name: str = None, config: Dict[str, Any] = None, **kwargs):
        raw_config = config or kwargs or {}
        self.cfg = GCPSubnetAtomicConfig(raw_config)
        
        if name is None:
            name = self.cfg.subnet_name
            
        super().__init__(name, raw_config)
        self.subnet: Optional[gcp.compute.Subnetwork] = None

    def create_infrastructure(self) -> Dict[str, Any]:
        """Create Subnet using SubnetworkComponent"""
        self.subnet = gcp.compute.Subnetwork(
            name=self.name,
            network_id=self.cfg.network_id,
            ip_cidr_range=self.cfg.ip_cidr_range,
            region=self.cfg.region,
            private_ip_google_access=self.cfg.private_ip_google_access,
            description=self.cfg.description,
            project=self.cfg.project
        )
        
        pulumi.export("subnet_id", self.subnet.id)
        pulumi.export("subnet_name", self.subnet.name)
        
        return self.get_outputs()

    def get_outputs(self) -> Dict[str, Any]:
        if not self.subnet:
            return {}
        return {
            "subnet_id": self.subnet.id,
            "subnet_name": self.subnet.name,
            "self_link": self.subnet.self_link,
            "ip_cidr_range": self.subnet.ip_cidr_range
        }

    @classmethod
    def get_metadata(cls):
        return {
            "name": "gcp-subnet-atomic",
            "title": "GCP Subnet",
            "description": "Standalone GCP Subnetwork resource.",
            "category": "networking",
            "provider": "gcp",
            "tier": "atomic"
        }
