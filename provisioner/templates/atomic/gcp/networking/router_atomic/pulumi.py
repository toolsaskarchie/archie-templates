"""
GCP Router Template
Creates a GCP Router using the RouterComponent.
"""
from typing import Any, Dict, Optional
import pulumi
import pulumi_gcp as gcp

from provisioner.templates.base import template_registry, InfrastructureTemplate
from .config import GCPRouterAtomicConfig

@template_registry("gcp-router-atomic")
class GCPRouterAtomicTemplate(InfrastructureTemplate):
    """
    GCP Router Template
    """
    
    def __init__(self, name: str = None, config: Dict[str, Any] = None, **kwargs):
        raw_config = config or kwargs or {}
        self.cfg = GCPRouterAtomicConfig(raw_config)
        
        if name is None:
            name = self.cfg.router_name
            
        super().__init__(name, raw_config)
        self.router: Optional[gcp.compute.Router] = None

    def create_infrastructure(self) -> Dict[str, Any]:
        """Create Router using RouterComponent"""
        self.router = gcp.compute.Router(
            name=self.name,
            network_id=self.cfg.network_id,
            region=self.cfg.region,
            project=self.cfg.project
        )
        
        pulumi.export("router_id", self.router.router.id)
        pulumi.export("router_name", self.router.router.name)
        
        return self.get_outputs()

    def get_outputs(self) -> Dict[str, Any]:
        if not self.router:
            return {}
        return {
            "router_id": self.router.router.id,
            "router_name": self.router.router.name,
            "self_link": self.router.router.self_link
        }

    @classmethod
    def get_metadata(cls):
        return {
            "name": "gcp-router-atomic",
            "title": "GCP Router",
            "description": "Standalone GCP Router resource.",
            "category": "networking",
            "provider": "gcp",
            "tier": "atomic"
        }
