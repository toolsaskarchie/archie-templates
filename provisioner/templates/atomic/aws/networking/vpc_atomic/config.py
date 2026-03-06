"""VPC Atomic Configuration"""
from dataclasses import dataclass
from typing import Any, Dict

@dataclass
class VPCAtomicConfig:
    """Configuration for atomic VPC"""
    vpc_name: str
    cidr_block: str
    project_name: str
    environment: str
    region: str
    enable_dns_hostnames: bool = True
    enable_dns_support: bool = True
    instance_tenancy: str = 'default'
    
    def __init__(self, config: Dict[str, Any]):
        self.project_name = config.get('projectName', 'my-project')
        self.environment = config.get('environment', 'dev')
        self.region = config.get('region', 'us-east-1')
        self.cidr_block = config.get('cidrBlock', 'auto-generated')
        
        # Generate VPC name with naming convention: vpc-[projectname]-[env]-[networkip]-[regionshortcode]
        self.vpc_name = self._generate_vpc_name()
        
        self.enable_dns_hostnames = config.get('enableDnsHostnames', True)
        self.enable_dns_support = config.get('enableDnsSupport', True)
        self.instance_tenancy = config.get('instanceTenancy', 'default')
        
        # Validate CIDR
        if not self.cidr_block:
            raise ValueError("cidrBlock is required")
        
        # Validate instance tenancy
        if self.instance_tenancy not in ['default', 'dedicated', 'host']:
            raise ValueError("instanceTenancy must be 'default', 'dedicated', or 'host'")
    
    def _generate_vpc_name(self) -> str:
        """Generate VPC name with convention: vpc-[projectname]-[env]-[networkip]-[regionshortcode]"""
        # Extract network IP from CIDR (first two octets)
        network_ip = self._get_network_ip_from_cidr()
        
        # Convert region to shortcode
        region_shortcode = self._get_region_shortcode()
        
        # Sanitize project name (remove special chars, limit length)
        project_clean = self._sanitize_name(self.project_name, 10)
        
        # Create name
        name = f"vpc-{project_clean}-{self.environment}-{network_ip}-{region_shortcode}"
        
        # Ensure total length doesn't exceed AWS limits (255 chars for tags)
        return name[:63]  # Leave room for other prefixes if needed
    
    def _get_network_ip_from_cidr(self) -> str:
        """Extract network IP from CIDR (e.g., '10.123.0.0/16' -> '10123')"""
        if self.cidr_block == 'auto-generated':
            # For auto-generated, we'll use a placeholder that gets updated after CIDR generation
            return 'auto'
        
        try:
            # Extract IP part before /
            ip_part = self.cidr_block.split('/')[0]
            # Get first two octets and join without dots
            octets = ip_part.split('.')[:2]
            return ''.join(octets)
        except (IndexError, ValueError):
            return '000'
    
    def _get_region_shortcode(self) -> str:
        """Convert AWS region to shortcode (e.g., 'us-east-1' -> 'use1')"""
        region_map = {
            'us-east-1': 'use1',
            'us-east-2': 'use2', 
            'us-west-1': 'usw1',
            'us-west-2': 'usw2',
            'eu-west-1': 'euw1',
            'eu-central-1': 'euc1',
            'ap-southeast-1': 'apse1',
            'ap-northeast-1': 'apne1',
            'ca-central-1': 'cac1',
            'sa-east-1': 'sae1',
            'ap-south-1': 'aps1',
            'eu-west-2': 'euw2',
            'eu-west-3': 'euw3',
            'eu-north-1': 'eun1',
            'ap-southeast-2': 'apse2',
            'ap-northeast-2': 'apne2',
            'ap-northeast-3': 'apne3',
            'ca-west-1': 'caw1',
            'af-south-1': 'afs1',
            'me-south-1': 'mes1'
        }
        return region_map.get(self.region, 'unk')
    
    def _sanitize_name(self, name: str, max_length: int = 20) -> str:
        """Sanitize name for AWS resource naming"""
        import re
        # Remove special characters, replace with hyphens
        sanitized = re.sub(r'[^a-zA-Z0-9]', '-', name.lower())
        # Remove multiple consecutive hyphens
        sanitized = re.sub(r'-+', '-', sanitized)
        # Remove leading/trailing hyphens
        sanitized = sanitized.strip('-')
        # Limit length
        return sanitized[:max_length]
