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
        self.config = raw_config

        # Resource references
        self.instance = None
        self.firewall_rules = []

    def _cfg(self, key: str, default=None):
        """Read config from root, parameters.gcp, or parameters (Rule #6)"""
        params = self.config.get('parameters', {})
        gcp_params = params.get('gcp', {}) if isinstance(params, dict) else {}
        return (
            self.config.get(key) or
            (gcp_params.get(key) if isinstance(gcp_params, dict) else None) or
            (params.get(key) if isinstance(params, dict) else None) or
            default
        )
    
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
        
        # Pulumi exports for stack outputs
        pulumi.export("instance_id", self.instance.id)
        pulumi.export("instance_name", self.instance.name)
        pulumi.export("internal_ip", self.instance.network_interfaces.apply(
            lambda interfaces: interfaces[0].network_ip if interfaces else "None"
        ))
        external_ip = self.instance.network_interfaces.apply(
            lambda interfaces: interfaces[0].access_configs[0].nat_ip
            if interfaces and interfaces[0].access_configs and len(interfaces[0].access_configs) > 0 and hasattr(interfaces[0].access_configs[0], 'nat_ip')
            else "None"
        )
        pulumi.export("external_ip", external_ip)
        pulumi.export("zone", self.cfg.zone)

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
            "base_cost": "$10/month",
            "tags": ["gcp", "compute", "vm"],
            "features": [
                "Compute Engine instance with configurable machine type",
                "Firewall rules for SSH, HTTP, HTTPS access",
                "Optional external IP address",
                "Configurable boot disk size and type",
                "Resource labeling for cost tracking",
            ],
            "complexity": "low",
            "deployment_time": "2-5 minutes",
            "marketplace_group": "gcp-compute-group",
            "use_cases": [
                "Development and testing virtual machines",
                "Application prototyping environments",
                "CI/CD build runners",
                "Lightweight application hosting",
            ],
            "pillars": [
                {
                    "title": "Operational Excellence",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Automated VM provisioning with configurable parameters.",
                    "practices": [
                        "Infrastructure as Code with Pulumi for repeatable deployments",
                        "Configurable machine type, disk size, and image selection",
                        "Allow stopping for update enables live configuration changes",
                        "Resource labeling for cost tracking and organization",
                        "SSH command output for immediate instance access"
                    ]
                },
                {
                    "title": "Security",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Firewall rules scoped to specific protocols and sources.",
                    "practices": [
                        "SSH access restricted to configurable source IP ranges",
                        "HTTP/HTTPS firewall rules are optional and independently toggled",
                        "Network tags isolate firewall rules to specific instances",
                        "Optional external IP assignment for private-only deployments"
                    ]
                },
                {
                    "title": "Reliability",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Single-instance deployment suitable for non-production workloads.",
                    "practices": [
                        "Configurable boot disk type for performance requirements",
                        "Zone-level deployment within regional infrastructure",
                        "Allow stopping for update prevents unexpected termination",
                        "Configurable disk size for workload-appropriate storage"
                    ]
                },
                {
                    "title": "Performance Efficiency",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Right-sized compute with configurable machine types.",
                    "practices": [
                        "Configurable machine type from e2-micro to n2-standard-8",
                        "SSD persistent disk option for I/O-intensive workloads",
                        "Configurable boot disk size up to 500 GB",
                        "Network interface with optional external IP for direct access"
                    ]
                },
                {
                    "title": "Cost Optimization",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Cost-effective compute for development and testing.",
                    "practices": [
                        "Default e2-micro instance type minimizes hourly costs",
                        "Optional external IP avoids static IP charges when not needed",
                        "Non-production sizing avoids over-provisioning",
                        "Single instance deployment with no redundant resources"
                    ]
                },
                {
                    "title": "Sustainability",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Right-sized instance with minimal resource waste.",
                    "practices": [
                        "E2 machine series uses dynamic resource management",
                        "Configurable sizing prevents over-provisioning",
                        "Google Cloud carbon-neutral infrastructure",
                        "Single instance avoids unnecessary redundancy for non-production"
                    ]
                }
            ]
        }

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        """Get configuration schema for the deploy form"""
        return {
            "type": "object",
            "properties": {
                "instance_name": {
                    "type": "string",
                    "default": "my-instance",
                    "title": "Instance Name",
                    "description": "Name for the Compute Engine instance",
                    "order": 1,
                    "group": "Essentials",
                    "isEssential": True,
                },
                "environment": {
                    "type": "string",
                    "default": "dev",
                    "title": "Environment",
                    "description": "Deployment environment",
                    "enum": ["dev", "staging"],
                    "order": 2,
                    "group": "Essentials",
                    "isEssential": True,
                },
                "machine_type": {
                    "type": "string",
                    "default": "e2-micro",
                    "title": "Machine Type",
                    "description": "GCP machine type for the instance",
                    "enum": ["e2-micro", "e2-small", "e2-medium", "n2-standard-2", "n2-standard-4", "n2-standard-8"],
                    "order": 10,
                    "group": "Compute",
                    "cost_impact": "$5-200/month",
                },
                "zone": {
                    "type": "string",
                    "default": "us-central1-a",
                    "title": "Zone",
                    "description": "GCP zone for the instance",
                    "order": 11,
                    "group": "Compute",
                },
                "disk_size_gb": {
                    "type": "number",
                    "default": 20,
                    "title": "Boot Disk Size (GB)",
                    "description": "Size of the boot disk",
                    "minimum": 10,
                    "maximum": 500,
                    "order": 12,
                    "group": "Compute",
                },
                "enable_http": {
                    "type": "boolean",
                    "default": True,
                    "title": "Enable HTTP",
                    "description": "Create firewall rule for HTTP (port 80)",
                    "order": 20,
                    "group": "Security & Access",
                },
                "enable_https": {
                    "type": "boolean",
                    "default": True,
                    "title": "Enable HTTPS",
                    "description": "Create firewall rule for HTTPS (port 443)",
                    "order": 21,
                    "group": "Security & Access",
                },
                "assign_external_ip": {
                    "type": "boolean",
                    "default": True,
                    "title": "External IP",
                    "description": "Assign an external IP address to the instance",
                    "order": 22,
                    "group": "Security & Access",
                },
                "team_name": {
                    "type": "string",
                    "default": "",
                    "title": "Team Name",
                    "description": "Team that owns this resource",
                    "order": 50,
                    "group": "Tags",
                },
            },
            "required": ["instance_name"],
        }
