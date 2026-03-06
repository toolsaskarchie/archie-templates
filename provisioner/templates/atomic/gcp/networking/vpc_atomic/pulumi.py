"""
GCP VPC Template
Creates a custom mode VPC network using the VPCComponent.
"""
from typing import Any, Dict, Optional
import pulumi
import pulumi_gcp as gcp

from provisioner.templates.base import template_registry, InfrastructureTemplate
from .config import GCPVPCAtomicConfig

@template_registry("gcp-vpc-atomic")
class GCPVPCAtomicTemplate(InfrastructureTemplate):
    """
    GCP VPC Template
    
    Creates a VPC network resource with:
    - Custom Mode (recommended)
    - Configurable Routing Mode
    - Description
    """
    
    def __init__(self, name: str = None, config: Dict[str, Any] = None, **kwargs):
        raw_config = config or kwargs or {}
        self.cfg = GCPVPCAtomicConfig(raw_config)
        
        if name is None:
            name = self.cfg.vpc_name
            
        super().__init__(name, raw_config)
        self.vpc: Optional[gcp.compute.Network] = None

    def create_infrastructure(self) -> Dict[str, Any]:
        """Create VPC directly - shows as actual GCP resource in preview"""
        # Ensure project is set for GCP resource creation
        if not self.cfg.project:
            raise ValueError("GCP project ID is required but not provided in configuration")
        
        # Create VPC directly (no ComponentResource wrapper)
        self.vpc = gcp.compute.Network(
            f"{self.name}-network",
            auto_create_subnetworks=self.cfg.auto_create_subnetworks,
            routing_mode=self.cfg.routing_mode,
            description=self.cfg.description or f"VPC network for {self.name}",
            project=self.cfg.project
        )
        
        pulumi.export("network_id", self.vpc.id)
        pulumi.export("network_name", self.vpc.name)
        
        return self.get_outputs()

    def get_outputs(self) -> Dict[str, Any]:
        if not self.vpc:
            return {}
        return {
            "network_id": self.vpc.id,
            "network_name": self.vpc.name,
            "self_link": self.vpc.self_link
        }

    @classmethod
    def get_metadata(cls):
        return {
            "name": "gcp-vpc-atomic",
            "title": "GCP VPC",
            "description": "Standalone GCP VPC network resource.",
            "category": "networking",
            "provider": "gcp",
            "tier": "atomic"
        }
