"""
Configuration parser for GCP VPC Non-Prod Template
"""
from typing import Dict, Any, Optional, List

class GCPVPCSimpleConfig:
    """Parsed and validated configuration for GCP VPC Non-Prod Template"""

    def __init__(self, raw_config: Dict[str, Any]):
        self.raw_config = raw_config
        self.parameters = self.raw_config.get('parameters', {}).get('gcp', {}) or self.raw_config.get('parameters', {})
        
        # Core attributes
        self.environment = self.raw_config.get('environment', 'nonprod')
        self.region = self.get_parameter('region') or self.raw_config.get('region', 'us-east1')
        self.tags = self.raw_config.get('tags', {})

    @property
    def project(self) -> str:
        """Get GCP Project ID with robust lookup."""
        # 1. Check parameters with various keys
        for key in ['project', 'projectId', 'project_id', 'gcp_project', 'projectName', 'project_name']:
            val = self.get_parameter(key)
            if val:
                return val
        
        # 2. Check credentials.gcp
        creds = self.raw_config.get('credentials', {})
        gcp_creds = creds.get('gcp', {})
        for key in ['project', 'projectId', 'project_id', 'gcp_project', 'projectName', 'project_name']:
            val = gcp_creds.get(key)
            if val:
                return val
        
        # 3. Check top-level credentials (fallback for malformed payloads)
        for key in ['project', 'projectId', 'project_id', 'gcp_project', 'projectName', 'project_name']:
            val = creds.get(key)
            if val:
                return val
                
        # 4. Last resort: return None (Atomic template will raise error)
        return None

    def get_parameter(self, key: str, default: Any = None) -> Any:
        """Get a parameter from the configuration."""
        return self.parameters.get(key, default)

    @property
    def project_name(self) -> str:
        """Get project name from config."""
        return (
            self.get_parameter('projectName') or
            self.get_parameter('project_name') or
            self.raw_config.get('projectName') or
            self.raw_config.get('project_name') or
            'gcp-vpc-nonprod'
        )

    @property
    def network_name(self) -> str:
        """Get network name, defaults to project_name."""
        return self.get_parameter('network_name', self.project_name)

    @property
    def routing_mode(self) -> str:
        """GCP Network routing mode: REGIONAL or GLOBAL."""
        return self.get_parameter('routing_mode', 'REGIONAL')

    @property
    def auto_create_subnetworks(self) -> bool:
        """Whether to auto-create subnetworks, defaults to False for precise control."""
        return self.get_parameter('auto_create_subnetworks', False)

    @property
    def public_subnet_cidr(self) -> str:
        """CIDR for the public subnet, defaults to '10.0.1.0/24'."""
        return self.get_parameter('public_subnet_cidr', '10.0.1.0/24')

    @property
    def private_subnet_cidr(self) -> str:
        """CIDR for the private subnet, defaults to '10.0.2.0/24'."""
        return self.get_parameter('private_subnet_cidr', '10.0.2.0/24')

    @property
    def enable_cloud_nat(self) -> bool:
        """Whether to enable Cloud NAT for private subnets, defaults to True."""
        return self.get_parameter('enable_cloud_nat', True)

    @property
    def firewall_rules(self) -> List[Dict[str, Any]]:
        """GCP Firewall rules (equivalent to AWS Security Groups)."""
        return self.get_parameter('firewall_rules', [
            {
                "name": "allow-ssh",
                "protocol": "tcp",
                "ports": ["22"],
                "source_ranges": ["0.0.0.0/0"]
            },
            {
                "name": "allow-web",
                "protocol": "tcp",
                "ports": ["80", "443"],
                "source_ranges": ["0.0.0.0/0"]
            }
        ])

    @staticmethod
    def get_config_schema() -> Dict[str, Any]:
        """Get JSON schema for UI configuration."""
        return {
            "type": "object",
            "properties": {
                "network_name": {
                    "type": "string",
                    "title": "Network Name",
                    "default": "gcp-vpc-nonprod"
                },
                "public_subnet_cidr": {
                    "type": "string",
                    "title": "Public Subnet CIDR",
                    "default": "10.0.1.0/24"
                },
                "private_subnet_cidr": {
                    "type": "string",
                    "title": "Private Subnet CIDR",
                    "default": "10.0.2.0/24"
                },
                "enable_cloud_nat": {
                    "type": "boolean",
                    "title": "Enable Cloud NAT",
                    "description": "Provide internet access to private instances",
                    "default": True
                }
            },
            "required": ["network_name"]
        }
