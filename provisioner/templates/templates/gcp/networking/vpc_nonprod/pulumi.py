"""
GCP VPC Simple Non-Prod Template - Pattern B Implementation

Creates a complete VPC (Virtual Private Cloud) network in GCP for non-production environments.
Includes a custom network, public/private subnets, firewall rules, and Cloud NAT for private internet access.
"""

from typing import Any, Dict, Optional, List
import pulumi

from provisioner.templates.base import template_registry, InfrastructureTemplate
from .config import GCPVPCSimpleConfig
from provisioner.utils.gcp.labels import get_vpc_labels, get_subnet_labels
from provisioner.utils.gcp.naming import get_vpc_name, get_subnet_name, get_firewall_rule_name
from provisioner.utils.cidr_calculator import calculate_subnet_cidrs
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory

@template_registry("gcp-vpc-nonprod")
class GCPVPCSimpleTemplate(InfrastructureTemplate):
    """
    GCP VPC Simple Non-Prod Template
    
    Creates a complete networking foundation in Google Cloud using factory pattern:
    - Custom Mode VPC Network
    - Public Subnet for internet-facing resources
    - Private Subnet for internal workloads
    - Firewall Rules for core protocols
    - Cloud Router & Cloud NAT for private subnet egress
    """

    def __init__(self, name: str = None, config: Dict[str, Any] = None, **kwargs):
        raw_config = config or kwargs or {}
        self.cfg = GCPVPCSimpleConfig(raw_config)
        
        if name is None:
            name = self.cfg.project_name
            
        super().__init__(name, raw_config)
        
        # Resource references
        self.vpc = None
        self.public_subnet = None
        self.private_subnet = None
        self.router = None
        self.nat = None
        self.firewall_rules = []

    def create_infrastructure(self) -> Dict[str, Any]:
        """Deploy GCP VPC infrastructure using factory pattern"""
        
        # Validate GCP project
        if not self.cfg.project:
            raise ValueError(
                "GCP project ID is required but not found. "
                "Please ensure 'project' or 'projectId' is provided in credentials or parameters."
            )
        
        print(f"[GCP VPC] Creating VPC in project: {self.cfg.project}")
        print(f"[GCP VPC] Region: {self.cfg.region}")
        
        # 1. Create VPC Network
        vpc_name = get_vpc_name(self.cfg.project_name, self.cfg.environment)
        self.vpc = factory.create(
            "gcp:compute:Network",
            vpc_name,
            project=self.cfg.project,
            auto_create_subnetworks=self.cfg.auto_create_subnetworks,
            routing_mode=self.cfg.routing_mode,
            description=f"VPC network for {self.cfg.project_name}"
        )

        # 2. Calculate Subnet CIDRs
        public_cidr = self.cfg.public_subnet_cidr
        private_cidr = self.cfg.private_subnet_cidr
        if "10.0" in public_cidr and "10.0" in private_cidr:
            v_public, v_private = calculate_subnet_cidrs("10.0.0.0/16", num_azs=2)
            public_cidr = public_cidr or v_public[0]
            private_cidr = private_cidr or v_private[0]

        # 3. Create Public Subnet
        public_subnet_name = get_subnet_name(self.cfg.project_name, self.cfg.environment, "public", self.cfg.region)
        self.public_subnet = factory.create(
            "gcp:compute:Subnetwork",
            public_subnet_name,
            network=self.vpc.id,
            ip_cidr_range=public_cidr,
            region=self.cfg.region,
            project=self.cfg.project,
            description="Public subnet for internet-facing resources"
        )

        # 4. Create Private Subnet
        private_subnet_name = get_subnet_name(self.cfg.project_name, self.cfg.environment, "private", self.cfg.region)
        self.private_subnet = factory.create(
            "gcp:compute:Subnetwork",
            private_subnet_name,
            network=self.vpc.id,
            ip_cidr_range=private_cidr,
            region=self.cfg.region,
            project=self.cfg.project,
            private_ip_google_access=True,
            description="Private subnet for internal workloads"
        )

        # 5. Create Cloud NAT if enabled
        if self.cfg.enable_cloud_nat:
            router_name = f"{self.name}-router"
            self.router = factory.create(
                "gcp:compute:Router",
                router_name,
                network=self.vpc.id,
                region=self.cfg.region,
                project=self.cfg.project
            )

            self.nat = factory.create(
                "gcp:compute:RouterNat",
                f"{self.name}-nat",
                router=self.router.name,
                region=self.cfg.region,
                project=self.cfg.project,
                nat_ip_allocate_option="AUTO_ONLY",
                source_subnetwork_ip_ranges_to_nat="ALL_SUBNETWORKS_ALL_IP_RANGES"
            )

        # 6. Create Firewalls
        for rule in self.cfg.firewall_rules:
            rule_name = get_firewall_rule_name(self.cfg.project_name, self.cfg.environment, rule['name'])
            fw = factory.create(
                "gcp:compute:Firewall",
                rule_name,
                network=self.vpc.id,
                project=self.cfg.project,
                allows=[{
                    "protocol": rule.get('protocol', 'tcp'),
                    "ports": rule.get('ports', [])
                }],
                source_ranges=rule.get('source_ranges', ['0.0.0.0/0']),
                description=f"Firewall rule: {rule['name']}"
            )
            self.firewall_rules.append(fw)

        return self.get_outputs()

    def get_outputs(self) -> Dict[str, Any]:
        """Get template outputs"""
        if not self.vpc: return {}
        return {
            "network_id": self.vpc.id,
            "network_name": self.vpc.name,
            "public_subnet_id": self.public_subnet.id if self.public_subnet else None,
            "private_subnet_id": self.private_subnet.id if self.private_subnet else None,
            "region": self.cfg.region,
            "project": self.cfg.project
        }

    @classmethod
    def get_metadata(cls) -> Dict[str, Any]:
        """Template metadata (Pattern B)"""
        return {
            "name": "gcp-vpc-nonprod",
            "title": "VPC Networking",
            "description": "Complete VPC network for GCP non-production environments with public/private subnets and Cloud NAT.",
            "category": "networking",
            "version": "1.1.0",
            "author": "InnovativeApps",
            "cloud": "gcp",
            "environment": "nonprod",
            "base_cost": "~$20/month",
            "tags": ["vpc", "networking", "gcp", "nonprod", "nat"],
            "complexity": "intermediate",
            "deployment_time": "3-5 minutes",
            "marketplace_group": "gcp-vpc-group"
        }

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        """Get configuration schema from source of truth"""
        return GCPVPCSimpleConfig.get_config_schema()
