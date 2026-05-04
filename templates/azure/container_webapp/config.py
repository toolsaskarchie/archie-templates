"""Configuration for Azure App Service Container Web App template."""
from typing import Dict, Any, Optional

class AzureContainerWebAppConfig:
    """Configuration for Azure Container Web App template"""
    
    def __init__(self, raw_config: Dict[str, Any]):
        """Parse configuration from user input"""
        self.raw_config = raw_config
        # Support both direct config and nested parameters structure
        params = raw_config.get('parameters', raw_config)

        # Core configuration
        self.appName = params.get('appName') or params.get('app_name')
        self.resourceGroup = params.get('resourceGroup') or params.get('resource_group')
        self.location = params.get('location', 'eastus')
        self.environment = params.get('environment', 'nonprod')
        self.region = self.raw_config.get('region', self.raw_config.get('location', 'eastus'))
        self.tags = self.raw_config.get('tags', {})
        
        # App Service configuration
        self.sku_tier = params.get('sku_tier', 'Free')
        self.sku_size = params.get('sku_size', 'F1')
        self.https_only = params.get('https_only', True)
        self.always_on = params.get('always_on', False)  # Not available in Free tier
        
        self._validate()
    
    def _validate(self):
        """Validate configuration"""
        # appName and resourceGroup are optional - will be auto-generated if not provided
        if not self.location:
            raise ValueError("location is required")