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
    allowed_ssh_sources: List[str] = field(default_factory=lambda: ["1.2.3.4/32"])
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
        self.region = config.get('region', 'us-central1')
        self.tags = config.get('tags', {})
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

    @staticmethod
    def get_config_schema() -> Dict[str, Any]:
        """Get JSON schema for UI configuration."""
        return {
            "type": "object",
            "properties": {
                "essentials_header": {
                    "type": "separator",
                    "title": "Template Essentials",
                    "group": "Essentials",
                    "isEssential": True,
                    "order": 0
                },
                "project_name": {
                    "type": "string",
                    "title": "Project Name",
                    "description": "Unique name for this deployment (lowercase, no spaces)",
                    "default": "compute-nonprod",
                    "group": "Essentials",
                    "isEssential": True,
                    "order": 1
                },
                "region": {
                    "type": "string",
                    "title": "GCP Region",
                    "description": "Region to deploy the instance",
                    "default": "us-central1",
                    "group": "Essentials",
                    "isEssential": True,
                    "order": 2
                },
                "compute_header": {
                    "type": "separator",
                    "title": "Compute Settings",
                    "group": "Compute Settings",
                    "isEssential": True,
                    "order": 10
                },
                "machine_type": {
                    "type": "string",
                    "title": "Machine Type",
                    "description": "GCP machine type for the instance",
                    "default": "e2-micro",
                    "group": "Compute Settings",
                    "isEssential": True,
                    "order": 11
                },
                "zone": {
                    "type": "string",
                    "title": "Zone",
                    "description": "GCP zone for the instance",
                    "default": "us-central1-a",
                    "group": "Compute Settings",
                    "isEssential": True,
                    "order": 12
                },
                "disk_size_gb": {
                    "type": "number",
                    "title": "Disk Size (GB)",
                    "description": "Boot disk size in gigabytes",
                    "default": 20,
                    "group": "Compute Settings",
                    "order": 13
                },
                "image": {
                    "type": "string",
                    "title": "OS Image",
                    "description": "Boot disk image (e.g., debian-cloud/debian-11)",
                    "default": "debian-cloud/debian-11",
                    "group": "Compute Settings",
                    "order": 14
                },
                "network_tags": {
                    "type": "array",
                    "title": "Network Tags",
                    "description": "Optional network tags for firewall rules",
                    "items": {"type": "string"},
                    "group": "Compute Settings",
                    "order": 15
                }
            },
            "required": ["project_name", "region", "machine_type", "zone"]
        }
