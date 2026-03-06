"""Configuration for Azure Static Website template."""
from typing import Dict, Any

class AzureStaticWebsiteConfig:
    """Configuration for Azure Static Website template"""
    
    def __init__(self, raw_config: Dict[str, Any]):
        """Parse configuration from user input"""
        self.websiteName = raw_config.get('websiteName')
        self.resourceGroup = raw_config.get('resourceGroup')
        self.location = raw_config.get('location', 'eastus')
        
        self._validate()
    
    def _validate(self):
        """Validate configuration"""
        if not self.websiteName:
            raise ValueError("websiteName is required")
        if not self.resourceGroup:
            raise ValueError("resourceGroup is required")