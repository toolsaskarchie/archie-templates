"""
GCP Compute Engine Non-Prod Configuration

Type-safe configuration for GCP VM instances.
"""
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class GcpComputeNonProdConfig:
    """Configuration for GCP Compute Engine Non-Prod"""
    
    # Instance settings
    instance_name: str = "compute-nonprod"
    machine_type: str = "e2-micro"
    zone: str = "us-central1-a"
    project: str = ""
    
    # Disk settings
    image: str = "debian-cloud/debian-11"
    disk_size_gb: int = 10
    disk_type: str = "pd-standard"
    
    # Network settings
    network: str = "default"
    subnetwork: str = ""
    assign_external_ip: bool = True
    
    # Firewall settings
    allowed_ssh_sources: List[str] = field(default_factory=lambda: ["0.0.0.0/0"])
    allowed_http_sources: List[str] = field(default_factory=lambda: ["0.0.0.0/0"])
    enable_http: bool = True
    enable_https: bool = False
    
    # Tags and labels
    environment: str = "nonprod"
    network_tags: List[str] = field(default_factory=list)
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize from config dictionary"""
        self.instance_name = config.get('instance_name', self.instance_name)
        self.machine_type = config.get('machine_type', self.machine_type)
        self.zone = config.get('zone', self.zone)
        self.project = config.get('project', self.project)
        
        # Disk
        self.image = config.get('image', self.image)
        self.disk_size_gb = int(config.get('disk_size_gb', self.disk_size_gb))
        self.disk_type = config.get('disk_type', self.disk_type)
        
        # Network
        self.network = config.get('network', self.network)
        self.subnetwork = config.get('subnetwork', self.subnetwork)
        self.assign_external_ip = config.get('assign_external_ip', self.assign_external_ip)
        
        # Firewall
        self.allowed_ssh_sources = config.get('allowed_ssh_sources', self.allowed_ssh_sources)
        self.allowed_http_sources = config.get('allowed_http_sources', self.allowed_http_sources)
        self.enable_http = config.get('enable_http', self.enable_http)
        self.enable_https = config.get('enable_https', self.enable_https)
        
        # Tags
        self.environment = config.get('environment', self.environment)
        self.network_tags = config.get('network_tags', self.network_tags)
    
    @property
    def resource_labels(self) -> Dict[str, str]:
        """Get resource labels"""
        return {
            'environment': self.environment,
            'managed-by': 'archie'
        }
    
    @property
    def computed_network_tags(self) -> List[str]:
        """Get computed network tags"""
        tags = list(self.network_tags)
        tags.append(f'{self.instance_name}-vm')
        if self.enable_http:
            tags.append('http-server')
        if self.enable_https:
            tags.append('https-server')
        return tags
