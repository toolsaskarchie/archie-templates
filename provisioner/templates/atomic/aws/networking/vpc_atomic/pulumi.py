"""
VPC Template
Creates a single VPC resource with DNS settings and CIDR configuration.
This is a true atomic resource - just the VPC, no subnets, gateways, or route tables.
"""
from typing import Any, Dict, Optional
import pulumi
import pulumi_aws as aws

from provisioner.templates.base import (
    InfrastructureTemplate,
    template_registry
)
from provisioner.utils.aws import get_standard_tags
from provisioner.templates.atomic.aws.networking.vpc_atomic.config import VPCAtomicConfig


@template_registry("aws-vpc-atomic")
class VPCAtomicTemplate(InfrastructureTemplate):
    """
    VPC Template
    
    Creates only a VPC resource with:
    - Configurable CIDR block
    - DNS hostname and resolution settings
    - Instance tenancy options
    - No subnets, gateways, or other resources
    """
    
    def __init__(self, name: str = None, config: Dict[str, Any] = None, **kwargs):
        """Initialize template"""
        raw_config = config or kwargs or {}
        
        if name is None:
            name = raw_config.get('vpcName', raw_config.get('projectName', 'vpc'))
        
        super().__init__(name, raw_config)
        self.cfg = VPCAtomicConfig(raw_config)
        
        # Resources
        self.vpc: Optional[aws.ec2.Vpc] = None
    
    def create_infrastructure(self) -> Dict[str, Any]:
        """Create VPC infrastructure directly - shows as actual AWS resource in preview"""
        tags = get_standard_tags(
            project=self.cfg.project_name,
            environment=self.cfg.environment,
            template="vpc-atomic"
        )

        # Always use provided CIDR or generate upfront (no temp VPC)
        if self.cfg.cidr_block == 'auto-generated':
            from provisioner.utils.aws.cidr_utils import generate_random_vpc_cidr
            actual_cidr = generate_random_vpc_cidr()
            print(f"[VPC ATOMIC] Auto-generated CIDR: {actual_cidr}")
        else:
            actual_cidr = self.cfg.cidr_block
        
        # Generate VPC name with the CIDR
        vpc_name = self._generate_final_vpc_name(actual_cidr)
        
        # Create single VPC directly (no ComponentResource wrapper)
        self.vpc = aws.ec2.Vpc(
            self.name,  # Use self.name directly (already contains vpc- prefix)
            cidr_block=actual_cidr,
            enable_dns_hostnames=self.cfg.enable_dns_hostnames,
            enable_dns_support=self.cfg.enable_dns_support,
            instance_tenancy=self.cfg.instance_tenancy,
            tags={**tags, "Name": vpc_name}
        )

        # Export outputs
        pulumi.export("vpc_id", self.vpc.id)
        pulumi.export("vpc_cidr", self.vpc.cidr_block)
        pulumi.export("vpc_name", vpc_name)

        return {
            "template_name": "vpc-atomic",
            "outputs": {
                "vpc_id": "Available after deployment",
                "vpc_cidr": actual_cidr,
                "vpc_name": vpc_name
            }
        }
    
    def get_outputs(self) -> Dict[str, Any]:
        """Get template outputs"""
        if not self.vpc:
            return {}

        return {
            "vpc_id": self.vpc.id,
            "vpc_cidr": self.vpc.cidr_block,
            "vpc_name": self.vpc.tags.get("Name", self.name)
        }
    
    def _generate_final_vpc_name(self, actual_cidr: str) -> str:
        """Generate VPC name with actual CIDR: vpc-[projectname]-[env]-[networkip]-[regionshortcode]"""
        # Extract network IP from actual CIDR
        network_ip = self._get_network_ip_from_actual_cidr(actual_cidr)
        
        # Convert region to shortcode
        region_shortcode = self._get_region_shortcode()
        
        # Sanitize project name
        project_clean = self._sanitize_name(self.cfg.project_name, 10)
        
        # Create name
        name = f"vpc-{project_clean}-{self.cfg.environment}-{network_ip}-{region_shortcode}"
        
        return name[:63]  # AWS resource name limit
    
    def _get_network_ip_from_actual_cidr(self, cidr: str) -> str:
        """Extract network IP from actual CIDR (e.g., '10.123.0.0/16' -> '10123')"""
        try:
            ip_part = cidr.split('/')[0]
            octets = ip_part.split('.')[:2]
            return ''.join(octets)
        except (IndexError, ValueError):
            return '000'
    
    def _get_region_shortcode(self) -> str:
        """Convert AWS region to shortcode"""
        region_map = {
            'us-east-1': 'use1', 'us-east-2': 'use2', 'us-west-1': 'usw1', 'us-west-2': 'usw2',
            'eu-west-1': 'euw1', 'eu-central-1': 'euc1', 'ap-southeast-1': 'apse1', 
            'ap-northeast-1': 'apne1', 'ca-central-1': 'cac1', 'sa-east-1': 'sae1',
            'ap-south-1': 'aps1', 'eu-west-2': 'euw2', 'eu-west-3': 'euw3', 
            'eu-north-1': 'eun1', 'ap-southeast-2': 'apse2', 'ap-northeast-2': 'apne2',
            'ap-northeast-3': 'apne3', 'ca-west-1': 'caw1', 'af-south-1': 'afs1', 
            'me-south-1': 'mes1'
        }
        return region_map.get(self.cfg.region, 'unk')
    
    def _sanitize_name(self, name: str, max_length: int = 20) -> str:
        """Sanitize name for AWS resource naming"""
        import re
        sanitized = re.sub(r'[^a-zA-Z0-9]', '-', name.lower())
        sanitized = re.sub(r'-+', '-', sanitized)
        sanitized = sanitized.strip('-')
        return sanitized[:max_length]
    
    @classmethod
    def get_metadata(cls) -> Dict[str, Any]:
        """Template metadata"""
        return {
            "name": "vpc-atomic",
            "title": "VPC",
            "subtitle": "Single VPC resource",
            "description": "Create a standalone VPC with configurable CIDR, DNS settings, and instance tenancy. This is an atomic resource containing only the VPC itself - no subnets, gateways, or route tables.",
            "category": "networking",
            "provider": "aws",
            "tier": "atomic",
            "complexity": "simple",
            "icon": "🌐",
            "version": "1.0.0",
            "status": "stable",
            "estimated_cost": "$0/month",
            "deployment_time": "1-2 minutes",
            "use_cases": [
                "Foundation for custom network architecture",
                "Expert users building networks manually",
                "Testing and learning VPC concepts"
            ],
            "features": [
                "Single VPC resource",
                "Configurable CIDR block",
                "DNS hostname support",
                "DNS resolution support",
                "Instance tenancy options"
            ],
            "outputs": [
                "VPC ID",
                "VPC CIDR block",
                "VPC name"
            ],
            "tags": [
                "vpc",
                "networking",
                "atomic",
                "foundation"
            ],
            "marketplace_group": "aws-vpc-group",
            "is_listed_in_marketplace": False
        }
    
    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        """JSON Schema for configuration"""
        return {
            "type": "object",
            "title": "VPC",
            "properties": {
                "vpcName": {
                    "type": "string",
                    "title": "VPC Name",
                    "description": "Name for the VPC (auto-generated)",
                    "default": "auto-generated"
                },
                "cidrBlock": {
                    "type": "string",
                    "title": "CIDR Block",
                    "description": "IPv4 CIDR block for the VPC",
                    "default": "10.0.0.0/16",
                    "pattern": "^([0-9]{1,3}\\.){3}[0-9]{1,3}/[0-9]{1,2}$"
                },
                "projectName": {
                    "type": "string",
                    "title": "Project Name",
                    "description": "Project name for tagging",
                    "default": "my-project"
                },
                "region": {
                    "type": "string",
                    "title": "AWS Region",
                    "description": "AWS region for VPC deployment",
                    "default": "us-east-1"
                },
                "environment": {
                    "type": "string",
                    "title": "Environment",
                    "enum": ["dev", "test", "staging", "prod"],
                    "default": "dev"
                },
                "enableDnsHostnames": {
                    "type": "boolean",
                    "title": "Enable DNS Hostnames",
                    "description": "Enable DNS hostnames in the VPC",
                    "default": true
                },
                "enableDnsSupport": {
                    "type": "boolean",
                    "title": "Enable DNS Support",
                    "description": "Enable DNS resolution in the VPC",
                    "default": true
                },
                "instanceTenancy": {
                    "type": "string",
                    "title": "Instance Tenancy",
                    "description": "Tenancy option for instances launched into the VPC",
                    "enum": ["default", "dedicated", "host"],
                    "default": "default"
                }
            },
            "required": ["cidrBlock", "projectName", "region"],
            "additionalProperties": false
        }
