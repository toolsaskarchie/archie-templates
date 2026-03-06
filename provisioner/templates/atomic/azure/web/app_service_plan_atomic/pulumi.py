"""Azure App Service Plan Template"""
from typing import Dict, Any, Optional
import pulumi
import pulumi_azure_native as azure

from provisioner.templates.atomic.base import AtomicTemplate


class AzureAppServicePlanAtomicTemplate(AtomicTemplate):
    """Azure App Service Plan Template
    
    Creates an Azure App Service Plan.
    
    Creates:
        - azure.web.AppServicePlan
    
    Outputs:
        - app_service_plan_name: Plan name
        - app_service_plan_id: Plan ID
    """
    
    def __init__(self, name: str, config: Dict[str, Any], **kwargs):
        """Initialize Azure App Service Plan atomic template"""
        super().__init__(name, config, **kwargs)
        self.plan_name = config.get('name')
        self.resource_group_name = config.get('resource_group_name')
        self.location = config.get('location')
        self.kind = config.get('kind', 'Linux')
        self.reserved = config.get('reserved', True)
        self.sku = config.get('sku')
        self.tags = config.get('tags', {})
        self.app_service_plan: Optional[azure.web.AppServicePlan] = None
    
    def create_infrastructure(self) -> Dict[str, Any]:
        """Create Azure App Service Plan"""
        self.app_service_plan = azure.web.AppServicePlan(
            f"{self.name}-plan",
            name=self.plan_name,
            resource_group_name=self.resource_group_name,
            location=self.location,
            kind=self.kind,
            reserved=self.reserved,
            sku=self.sku,
            tags=self.tags,
            opts=self.resource_options
        )
        
        pulumi.export(f"{self.name}_app_service_plan_name", self.app_service_plan.name)
        pulumi.export(f"{self.name}_app_service_plan_id", self.app_service_plan.id)
        
        return self.get_outputs()
    
    def get_outputs(self) -> Dict[str, Any]:
        """Get App Service Plan outputs"""
        if not self.app_service_plan:
            raise RuntimeError(f"App Service Plan {self.name} not created")
        
        return {
            "app_service_plan_name": self.app_service_plan.name,
            "app_service_plan_id": self.app_service_plan.id,
        }
