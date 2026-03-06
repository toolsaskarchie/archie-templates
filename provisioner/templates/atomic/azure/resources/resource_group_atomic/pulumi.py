"""Azure Resource Group Template

TODO: Refactor to use ResourceGroupComponent once it's created.
Component should be located at: provisioner/components/azure/resources/resource_group_component.py
"""
from typing import Dict, Any, Optional
import pulumi
import pulumi_azure_native as azure

from provisioner.templates.atomic.base import AtomicTemplate


class AzureResourceGroupAtomicTemplate(AtomicTemplate):
    """Azure Resource Group Template
    
    Creates an Azure Resource Group.
    
    Creates:
        - azure.resources.ResourceGroup
    
    Outputs:
        - resource_group_name: Resource group name
        - location: Resource group location
    """
    
    def __init__(self, name: str, config: Dict[str, Any], **kwargs):
        """Initialize Azure Resource Group atomic template"""
        super().__init__(name, config, **kwargs)
        self.resource_group_name = config.get('resource_group_name')
        self.location = config.get('location')
        self.tags = config.get('tags', {})
        self.resource_group: Optional[azure.resources.ResourceGroup] = None
    
    def create_infrastructure(self) -> Dict[str, Any]:
        """Create Azure Resource Group"""
        self.resource_group = azure.resources.ResourceGroup(
            f"{self.name}-rg",
            resource_group_name=self.resource_group_name,
            location=self.location,
            tags=self.tags,
            opts=self.resource_options
        )
        
        pulumi.export(f"{self.name}_resource_group_name", self.resource_group.name)
        pulumi.export(f"{self.name}_location", self.resource_group.location)
        
        return self.get_outputs()
    
    def get_outputs(self) -> Dict[str, Any]:
        """Get Resource Group outputs"""
        if not self.resource_group:
            raise RuntimeError(f"Resource Group {self.name} not created")
        
        return {
            "resource_group_name": self.resource_group.name,
            "location": self.resource_group.location,
            "resource_group_id": self.resource_group.id,
        }
