"""
GCP NAT Template
Creates a GCP Router NAT using the RouterNatComponent.
"""
from typing import Any, Dict, Optional
import pulumi
import pulumi_gcp as gcp

from provisioner.templates.base import template_registry, InfrastructureTemplate
from .config import GCPNATAtomicConfig

@template_registry("gcp-nat-atomic")
class GCPNATAtomicTemplate(InfrastructureTemplate):
    """
    GCP NAT Template
    """
    
    def __init__(self, name: str = None, config: Dict[str, Any] = None, **kwargs):
        raw_config = config or kwargs or {}
        self.cfg = GCPNATAtomicConfig(raw_config)
        
        if name is None:
            name = self.cfg.nat_name
            
        super().__init__(name, raw_config)
        self.nat: Optional[gcp.compute.RouterNat] = None

    def create_infrastructure(self) -> Dict[str, Any]:
        """Create NAT using RouterNatComponent"""
        self.nat = gcp.compute.RouterNat(
            name=self.name,
            router_name=self.cfg.router_name,
            region=self.cfg.region,
            nat_ip_allocate_option=self.cfg.nat_ip_allocate_option,
            source_subnetwork_ip_ranges_to_nat=self.cfg.source_subnetwork_ip_ranges_to_nat,
            project=self.cfg.project
        )
        
        pulumi.export("nat_id", self.nat.id)
        pulumi.export("nat_name", self.nat.name)
        
        return self.get_outputs()

    def get_outputs(self) -> Dict[str, Any]:
        if not self.nat:
            return {}
        return {
            "nat_id": self.nat.id,
            "nat_name": self.nat.name
        }

    @classmethod
    def get_metadata(cls):
        return {
            "name": "gcp-nat-atomic",
            "title": "GCP NAT",
            "description": "Standalone GCP Router NAT resource.",
            "category": "networking",
            "provider": "gcp",
            "tier": "atomic"
        }
