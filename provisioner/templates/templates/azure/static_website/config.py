"""Configuration for Azure Static Website template."""
from typing import Dict, Any

class AzureStaticWebsiteConfig:
    """Configuration for Azure Static Website template"""
    
    def __init__(self, raw_config: Dict[str, Any]):
        """Parse configuration from user input"""
        project = raw_config.get('projectName', raw_config.get('project_name', 'azure-site'))
        self.websiteName = raw_config.get('websiteName') or project
        self.resourceGroup = raw_config.get('resourceGroup') or f"rg-{self.websiteName}"
        self.location = raw_config.get('location', 'eastus')