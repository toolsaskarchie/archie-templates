"""
Azure VNet Template

Creates a single Azure Virtual Network resource with configurable address spaces.
This is a true atomic resource - just the VNet, no subnets, NSGs, or other resources.
"""
from typing import Any, Dict, Optional
import pulumi
import pulumi_azure_native as azure

from provisioner.templates.base import (
    InfrastructureTemplate,
    template_registry
)
from provisioner.templates.atomic.azure.networking.vnet_atomic.config import VNetAtomicConfig

@template_registry("azure-vnet-atomic")
class AzureVNetAtomicTemplate(InfrastructureTemplate):
    """
    Azure VNet Template
    
    Creates only a Virtual Network resource with:
    - Configurable address space (CIDR blocks)
    - Resource group (auto-created if doesn't exist)
    - Location/region
    - Tags for organization
    - No subnets, NSGs, or other resources
    """
    
    def __init__(self, name: str = None, config: Dict[str, Any] = None, **kwargs):
        """Initialize template"""
        raw_config = config or kwargs or {}
        
        if name is None:
            name = raw_config.get('vnetName', raw_config.get('projectName', 'azure-vnet'))
        
        super().__init__(name, raw_config)
        self.cfg = VNetAtomicConfig(raw_config)
        
        # Resources
        self.resource_group: Optional[azure.resources.ResourceGroup] = None
        self.vnet: Optional[azure.network.VirtualNetwork] = None
    
    def create_infrastructure(self) -> Dict[str, Any]:
        """Create VNet infrastructure using VNetComponent"""
        
        # Prepare tags
        tags = {
            "project": self.cfg.project_name,
            "environment": self.cfg.environment,
            "managed-by": "archie",
            "template": "azure-vnet-atomic"
        }
        
        print(f"[AZURE-VNET-ATOMIC] Creating infrastructure...")
        print(f"  VNet Name: {self.cfg.vnet_name}")
        print(f"  Resource Group: {self.cfg.resource_group_name}")
        print(f"  Location: {self.cfg.location}")
        print(f"  Address Prefixes: {', '.join(self.cfg.address_prefixes)}")
        
        # Create Resource Group
        self.resource_group = azure.resources.ResourceGroup(
            f"{self.name}-rg",
            resource_group_name=self.cfg.resource_group_name,
            location=self.cfg.location,
            tags=tags
        )
        print(f"  ✓ Created resource group: {self.cfg.resource_group_name}")
        
        # Create VNet using component
        self.vnet = azure.network.VirtualNetwork(
            name=self.name,
            resource_group_name=self.resource_group.name,
            location=self.cfg.location,
            virtual_network_name=self.cfg.vnet_name,
            address_prefixes=self.cfg.address_prefixes,
            tags=tags
        )
        print(f"  ✓ Created VNet: {self.cfg.vnet_name}")
        
        # Export outputs
        pulumi.export("vnet_id", self.vnet.id)
        pulumi.export("vnet_name", self.vnet.name)
        pulumi.export("resource_group_name", self.resource_group.name)
        pulumi.export("location", self.cfg.location)
        pulumi.export("address_prefixes", self.vnet.address_space.address_prefixes)
        pulumi.export("congratulations_message", 
            f"🎉 Your Azure VNet '{self.cfg.vnet_name}' has been successfully deployed!")
        
        print(f"[AZURE-VNET-ATOMIC] Infrastructure created successfully!")
        
        return {
            "template_name": "azure-vnet-atomic",
            "outputs": {
                "vnet_id": "Available after deployment",
                "vnet_name": self.cfg.vnet_name,
                "resource_group_name": self.cfg.resource_group_name,
                "location": self.cfg.location,
                "address_prefixes": self.cfg.address_prefixes
            }
        }
    
    def get_outputs(self) -> Dict[str, Any]:
        """Get template outputs"""
        if not self.vnet:
            return {}
        
        return {
            "vnet_id": self.vnet.id,
            "vnet_name": self.vnet.name,
            "resource_group_name": self.cfg.resource_group_name,
            "location": self.cfg.location,
            "address_prefixes": self.cfg.address_prefixes
        }
    
    @classmethod
    def get_metadata(cls) -> Dict[str, Any]:
        """Template metadata"""
        return {
            "name": "azure-vnet-atomic",
            "title": "Azure Virtual Network",
            "subtitle": "Single VNet resource",
            "description": "Create a standalone Azure Virtual Network with configurable address space. This is an atomic resource containing only the VNet itself - no subnets, NSGs, or route tables.",
            "category": "networking",
            "provider": "azure",
            "tier": "atomic",
            "complexity": "simple",
            "icon": "🌐",
            "version": "1.0.0",
            "status": "stable",
            "estimated_cost": "$0/month (VNet is free)",
            "deployment_time": "1-2 minutes",
            "use_cases": [
                "Foundation for custom Azure network architecture",
                "Expert users building networks manually",
                "Testing and learning Azure VNet concepts",
                "Multi-tier network designs"
            ],
            "features": [
                "Single VNet resource",
                "Configurable address space (one or more CIDR blocks)",
                "Automatic resource group creation",
                "Azure region/location selection",
                "Resource tagging for organization"
            ],
            "outputs": [
                "VNet ID",
                "VNet name",
                "Resource group name",
                "Location",
                "Address prefixes"
            ],
            "tags": [
                "vnet",
                "networking",
                "azure",
                "atomic",
                "foundation"
            ]
        }
    
    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        """JSON Schema for configuration"""
        return {
            "type": "object",
            "title": "Azure VNet",
            "properties": {
                "vnetName": {
                    "type": "string",
                    "title": "VNet Name",
                    "description": "Name for the Virtual Network",
                    "default": "my-vnet"
                },
                "resourceGroupName": {
                    "type": "string",
                    "title": "Resource Group Name",
                    "description": "Name for the resource group (auto-generated if not provided)",
                    "default": ""
                },
                "location": {
                    "type": "string",
                    "title": "Location",
                    "description": "Azure region for the VNet",
                    "enum": [
                        "eastus",
                        "eastus2",
                        "westus",
                        "westus2",
                        "westus3",
                        "centralus",
                        "northcentralus",
                        "southcentralus",
                        "westcentralus",
                        "canadacentral",
                        "canadaeast",
                        "brazilsouth",
                        "northeurope",
                        "westeurope",
                        "uksouth",
                        "ukwest",
                        "francecentral",
                        "germanywestcentral",
                        "norwayeast",
                        "switzerlandnorth",
                        "swedencentral",
                        "australiaeast",
                        "australiasoutheast",
                        "southeastasia",
                        "eastasia",
                        "japaneast",
                        "japanwest",
                        "koreacentral",
                        "koreasouth",
                        "southindia",
                        "centralindia",
                        "westindia",
                        "uaenorth"
                    ],
                    "default": "eastus"
                },
                "addressPrefixes": {
                    "type": "string",
                    "title": "Address Prefixes",
                    "description": "CIDR block(s) for the VNet address space (comma-separated for multiple)",
                    "default": "10.0.0.0/16",
                    "pattern": "^([0-9]{1,3}\\.){3}[0-9]{1,3}/[0-9]{1,2}(,\\s*([0-9]{1,3}\\.){3}[0-9]{1,3}/[0-9]{1,2})*$"
                },
                "projectName": {
                    "type": "string",
                    "title": "Project Name",
                    "description": "Project name for tagging and organization",
                    "default": "my-project"
                },
                "environment": {
                    "type": "string",
                    "title": "Environment",
                    "description": "Environment type",
                    "enum": ["dev", "test", "staging", "prod"],
                    "default": "dev"
                }
            },
            "required": ["vnetName", "location", "addressPrefixes"]
        }
