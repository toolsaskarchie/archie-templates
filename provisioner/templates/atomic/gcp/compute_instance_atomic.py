"""
GCP Compute Instance Atomic Template

Google Cloud Compute Engine VM instance - uses direct GCP resources.
"""
from typing import Any, Dict, List, Optional
import pulumi
import pulumi_gcp as gcp

from provisioner.templates.atomic.base import AtomicTemplate


class GcpComputeInstanceAtomicTemplate(AtomicTemplate):
    """
    GCP Compute Instance Atomic - Creates a Compute Engine VM directly
    
    Configuration:
        name: Instance name
        machine_type: Machine type (e.g., e2-micro, n1-standard-1)
        zone: GCP zone
        project: GCP project ID
        network: Network name or self_link
        subnetwork: Subnetwork name or self_link
        image: Boot disk image (e.g., debian-cloud/debian-11)
        disk_size_gb: Boot disk size in GB
        disk_type: Disk type (pd-standard, pd-ssd, pd-balanced)
        tags: Network tags for firewall rules
        metadata: Instance metadata
        labels: Resource labels
        allow_stopping_for_update: Allow stopping for updates
    
    Outputs:
        instance_id: Instance ID
        instance_name: Instance name
        internal_ip: Internal IP address
        external_ip: External IP address (if assigned)
        self_link: Instance self link
    """
    
    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.instance: Optional[gcp.compute.Instance] = None
        self._outputs = {}
    
    def create_infrastructure(self) -> Dict[str, Any]:
        """Create GCP Compute Engine instance directly - shows as actual GCP resource in preview"""
        
        instance_name = self.config.get('name', self.name)
        machine_type = self.config.get('machine_type', 'e2-micro')
        zone = self.config.get('zone', 'us-central1-a')
        
        # Boot disk configuration
        boot_disk = {
            'initialize_params': {
                'image': self.config.get('image', 'debian-cloud/debian-11'),
                'size': self.config.get('disk_size_gb', 10),
                'type': self.config.get('disk_type', 'pd-standard')
            }
        }
        
        # Network configuration
        network = self.config.get('network', 'default')
        subnetwork = self.config.get('subnetwork')
        assign_external_ip = self.config.get('assign_external_ip', True)
        
        # Build network interface
        network_interface = {
            'network': network,
        }
        
        if subnetwork:
            network_interface['subnetwork'] = subnetwork
        
        if assign_external_ip:
            network_interface['access_config'] = {}
        
        # Create instance directly (no ComponentResource wrapper)
        self.instance = gcp.compute.Instance(
            f"{self.name}-instance",
            name=instance_name,
            machine_type=machine_type,
            zone=zone,
            boot_disk=boot_disk,
            network_interfaces=[network_interface],
            project=self.config.get('project'),
            metadata=self.config.get('metadata', {}),
            tags=self.config.get('tags', []),
            labels=self.config.get('labels', {}),
            allow_stopping_for_update=self.config.get('allow_stopping_for_update', True)
        )
        
        # Get external IP if assigned
        external_ip = None
        if assign_external_ip:
            external_ip = self.instance.network_interfaces[0].access_configs[0].nat_ip
        
        outputs = {
            'instance_id': self.instance.id,
            'instance_name': self.instance.name,
            'internal_ip': self.instance.network_interfaces[0].network_ip,
            'external_ip': external_ip,
            'self_link': self.instance.self_link,
            'zone': self.instance.zone
        }
        
        self._outputs = outputs
        return outputs

    def get_outputs(self) -> Dict[str, Any]:
        """Get template outputs"""
        return self._outputs

    def get_metadata(self) -> Dict[str, Any]:
        """Get template metadata"""
        return {
            "name": "gcp-compute-instance-atomic",
            "title": "GCP Compute Instance",
            "description": "Atomic GCP Compute Engine VM instance.",
            "category": "compute",
            "provider": "gcp",
            "tier": "atomic"
        }
