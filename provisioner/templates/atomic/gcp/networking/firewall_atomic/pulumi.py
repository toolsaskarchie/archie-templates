"""
GCP Firewall Template
Creates a GCP Firewall rule using the FirewallComponent.
"""
from typing import Any, Dict, Optional
import pulumi
import pulumi_gcp as gcp

from provisioner.templates.base import template_registry, InfrastructureTemplate
from .config import GCPFirewallAtomicConfig

@template_registry("gcp-firewall-atomic")
class GCPFirewallAtomicTemplate(InfrastructureTemplate):
    """
    GCP Firewall Template
    """
    
    def __init__(self, name: str = None, config: Dict[str, Any] = None, **kwargs):
        raw_config = config or kwargs or {}
        self.cfg = GCPFirewallAtomicConfig(raw_config)
        
        if name is None:
            name = self.cfg.firewall_name
            
        super().__init__(name, raw_config)
        self.firewall: Optional[gcp.compute.Firewall] = None

    def create_infrastructure(self) -> Dict[str, Any]:
        """Create Firewall using FirewallComponent"""
        self.firewall = gcp.compute.Firewall(
            f"{self.name}-firewall",
            name=self.cfg.firewall_name,
            network=self.cfg.network_id,
            allows=self.cfg.allows,
            source_ranges=self.cfg.source_ranges,
            description=self.cfg.description,
            project=self.cfg.project
        )
        
        pulumi.export("firewall_id", self.firewall.id)
        pulumi.export("firewall_name", self.firewall.name)
        
        return self.get_outputs()

    def get_outputs(self) -> Dict[str, Any]:
        if not self.firewall:
            return {}
        return {
            "firewall_id": self.firewall.id,
            "firewall_name": self.firewall.name,
            "self_link": self.firewall.self_link
        }

    @classmethod
    def get_metadata(cls):
        return {
            "name": "gcp-firewall-atomic",
            "title": "GCP Firewall",
            "description": "Standalone GCP Firewall resource.",
            "category": "networking",
            "provider": "gcp",
            "tier": "atomic"
        }
