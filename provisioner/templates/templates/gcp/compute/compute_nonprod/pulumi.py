"""
GCP Compute Engine Non-Prod Template - Pattern B Implementation

Deploys a GCP Compute Engine VM instance for development and testing:
- Compute Engine instance with configurable machine type
- Firewall rules for SSH, HTTP, HTTPS access
- External IP address (optional)
- Boot disk with configurable size and type
"""

from typing import Any, Dict, List
import pulumi

from provisioner.templates.base import InfrastructureTemplate, template_registry
from .config import GcpComputeNonProdConfig
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory

@template_registry("gcp-compute-nonprod")
class GcpComputeNonProdTemplate(InfrastructureTemplate):
    """
    GCP Compute Engine Non-Prod Template
    
    Deploys VM instance for development/testing using factory pattern.
    """
    
    def __init__(self, name: str = None, config: Dict[str, Any] = None, **kwargs):
        """Initialize template"""
        raw_config = config or kwargs or {}
        self.cfg = GcpComputeNonProdConfig(raw_config)
        
        if name is None:
            name = self.cfg.instance_name
        
        super().__init__(name, raw_config)
        
        # Resource references
        self.instance = None
        self.firewall_rules = []
    
    def create_infrastructure(self) -> Dict[str, Any]:
        """Deploy infrastructure (implements abstract method)"""
        return self.create()

    def create(self) -> Dict[str, Any]:
        """Deploy GCP Compute Engine infrastructure using factory pattern"""
        instance_name = self.cfg.instance_name
        project = self.cfg.project
        
        print(f"[GCP-COMPUTE-NONPROD] Creating instance: {instance_name}")
        
        # 1. Firewall Rules
        # SSH access
        ssh_fw = factory.create(
            "gcp:compute:Firewall",
            f"{instance_name}-allow-ssh",
            name=f"{instance_name}-allow-ssh",
            network=self.cfg.network,
            project=project,
            source_ranges=self.cfg.allowed_ssh_sources,
            target_tags=[f"{instance_name}-vm"],
            allows=[{"protocol": "tcp", "ports": ["22"]}],
            description=f"Allow SSH access to {instance_name}"
        )
        self.firewall_rules.append(ssh_fw)
        
        # HTTP
        if self.cfg.enable_http:
            http_fw = factory.create(
                "gcp:compute:Firewall",
                f"{instance_name}-allow-http",
                name=f"{instance_name}-allow-http",
                network=self.cfg.network,
                project=project,
                source_ranges=self.cfg.allowed_http_sources,
                target_tags=["http-server"],
                allows=[{"protocol": "tcp", "ports": ["80"]}],
                description=f"Allow HTTP access to {instance_name}"
            )
            self.firewall_rules.append(http_fw)
            
        # HTTPS
        if self.cfg.enable_https:
            https_fw = factory.create(
                "gcp:compute:Firewall",
                f"{instance_name}-allow-https",
                name=f"{instance_name}-allow-https",
                network=self.cfg.network,
                project=project,
                source_ranges=self.cfg.allowed_http_sources,
                target_tags=["https-server"],
                allows=[{"protocol": "tcp", "ports": ["443"]}],
                description=f"Allow HTTPS access to {instance_name}"
            )
            self.firewall_rules.append(https_fw)

        # 2. Compute Instance
        self.instance = factory.create(
            "gcp:compute:Instance",
            instance_name,
            machine_type=self.cfg.machine_type,
            zone=self.cfg.zone,
            project=project,
            boot_disk={
                "initialize_params": {
                    "image": self.cfg.image,
                    "size": self.cfg.disk_size_gb,
                    "type": self.cfg.disk_type
                }
            },
            network_interfaces=[{
                "network": self.cfg.network,
                "subnetwork": self.cfg.subnetwork if self.cfg.subnetwork else None,
                "access_configs": [{}] if self.cfg.assign_external_ip else []
            }],
            tags=self.cfg.computed_network_tags,
            labels=self.cfg.resource_labels,
            allow_stopping_for_update=True
        )
        
        return self.get_outputs()

    def get_outputs(self) -> Dict[str, Any]:
        """Get template outputs"""
        if not self.instance: return {}
        
        # Build connection command
        ssh_command = pulumi.Output.concat(
            'gcloud compute ssh ', self.instance.name, ' --zone=', self.cfg.zone
        )
        if self.cfg.project:
            ssh_command = pulumi.Output.concat(ssh_command, ' --project=', self.cfg.project)
            
        external_ip = self.instance.network_interfaces.apply(
            lambda interfaces: interfaces[0].access_configs[0].nat_ip if interfaces and interfaces[0].access_configs and len(interfaces[0].access_configs) > 0 and hasattr(interfaces[0].access_configs[0], 'nat_ip') else "None"
        )
        
        return {
            "instance_id": self.instance.id,
            "instance_name": self.instance.name,
            "internal_ip": self.instance.network_interfaces.apply(lambda interfaces: interfaces[0].network_ip if interfaces else "None"),
            "external_ip": external_ip,
            "zone": self.cfg.zone,
            "ssh_command": ssh_command
        }

    @classmethod
    def get_metadata(cls) -> Dict[str, Any]:
        """Template metadata (Pattern B)"""
        return {
            "name": "gcp-compute-nonprod",
            "title": "Compute Engine Instance",
            "description": "Standard virtual machine instance in Google Cloud Platform for development and testing.",
            "category": "compute",
            "version": "1.1.0",
            "author": "InnovativeApps",
            "cloud": "gcp",
            "environment": "nonprod",
            "base_cost": "$30/month",
            "tags": ["gcp", "compute", "vm"],
            "complexity": "low",
            "deployment_time": "2-5 minutes",
            "marketplace_group": "gcp-compute-group"
        }
