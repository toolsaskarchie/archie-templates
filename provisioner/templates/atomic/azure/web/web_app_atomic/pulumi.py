"""Azure Web App Template"""
from typing import Dict, Any, Optional
import pulumi
import pulumi_azure_native as azure

from provisioner.templates.atomic.base import AtomicTemplate


class AzureWebAppAtomicTemplate(AtomicTemplate):
    """Azure Web App Template
    
    Creates an Azure Web App (App Service).
    
    Creates:
        - azure.web.WebApp
    
    Outputs:
        - web_app_name: App name
        - default_host_name: App default hostname
    """
    
    def __init__(self, name: str, config: Dict[str, Any], **kwargs):
        """Initialize Azure Web App atomic template"""
        super().__init__(name, config, **kwargs)
        self.app_name = config.get('name')
        self.resource_group_name = config.get('resource_group_name')
        self.location = config.get('location')
        self.server_farm_id = config.get('server_farm_id')
        self.https_only = config.get('https_only', True)
        self.site_config = config.get('site_config')
        self.tags = config.get('tags', {})
        self.web_app: Optional[azure.web.WebApp] = None
    
    def create_infrastructure(self) -> Dict[str, Any]:
        """Create Azure Web App"""
        self.web_app = azure.web.WebApp(
            f"{self.name}-app",
            name=self.app_name,
            resource_group_name=self.resource_group_name,
            location=self.location,
            server_farm_id=self.server_farm_id,
            https_only=self.https_only,
            site_config=self.site_config,
            tags=self.tags,
            opts=self.resource_options
        )
        
        pulumi.export(f"{self.name}_web_app_name", self.web_app.name)
        pulumi.export(f"{self.name}_default_host_name", self.web_app.default_host_name)
        
        return self.get_outputs()
    
    def get_outputs(self) -> Dict[str, Any]:
        """Get Web App outputs"""
        if not self.web_app:
            raise RuntimeError(f"Web App {self.name} not created")
        
        return {
            "web_app_name": self.web_app.name,
            "default_host_name": self.web_app.default_host_name,
            "web_app_id": self.web_app.id,
        }
