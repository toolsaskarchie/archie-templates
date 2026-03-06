"""
Azure Static Website Template - Pattern B Implementation

Deploys an Archie-branded static website to Azure Storage.
Uses PulumiAtomicFactory for resource creation and standardized metadata.
"""

from typing import Any, Dict, Optional
import random
import string
import pulumi
from provisioner.templates.base import template_registry, InfrastructureTemplate
from .config import AzureStaticWebsiteConfig
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory


@template_registry("azure-static-website")
class AzureStaticWebsiteTemplate(InfrastructureTemplate):
    """
    Azure Static Website Template
    
    Creates:
    - Azure Resource Group
    - Azure Storage Account with static website hosting
    """
    
    def __init__(self, name: str = None, config: Dict[str, Any] = None, **kwargs):
        """Initialize Azure static website template"""
        raw_config = config or kwargs or {}
        if name is None:
            name = raw_config.get('websiteName', 'azure-static-website')
        super().__init__(name, raw_config)
        self.cfg = AzureStaticWebsiteConfig(raw_config)
        self.resource_group = None
        self.storage_account = None

    def create_infrastructure(self) -> Dict[str, Any]:
        """Deploy infrastructure using factory pattern"""
        random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
        
        # 1. Resource Group
        self.resource_group = factory.create(
            "azure-native:resources:ResourceGroup",
            f"{self.name}-rg",
            resource_group_name=self.cfg.resourceGroup or f"rg-{self.name}-{random_suffix}",
            location=self.cfg.location,
            tags={"ManagedBy": "Archie", "Template": "azure-static-website"}
        )
        
        # 2. Storage Account
        sa_name = f"st{self.name.replace('-', '')[:14]}{random_suffix}"[:24].lower()
        self.storage_account = factory.create(
            "azure-native:storage:StorageAccount",
            f"{self.name}-storage",
            account_name=sa_name,
            resource_group_name=self.resource_group.name,
            location=self.cfg.location,
            sku={"name": "Standard_LRS"},
            kind="StorageV2",
            enable_https_traffic_only=True,
            tags={"ManagedBy": "Archie"}
        )
        
        # 3. Static Website Enablement
        factory.create(
            "azure-native:storage:StorageAccountStaticWebsite",
            f"{self.name}-static",
            account_name=self.storage_account.name,
            resource_group_name=self.resource_group.name,
            index_document="index.html",
            error404_document="index.html"
        )
        
        # 4. Construct URL
        website_url = self.storage_account.primary_endpoints.apply(
            lambda e: e.web if e and hasattr(e, 'web') else "pending"
        )
        
        pulumi.export("website_name", self.name)
        pulumi.export("resource_group", self.resource_group.name)
        pulumi.export("storage_account_name", self.storage_account.name)
        pulumi.export("website_url", website_url)
        
        return {
            "template_name": "azure-static-website",
            "outputs": {
                "website_name": self.name,
                "resource_group": self.resource_group.name,
                "storage_account_name": self.storage_account.name,
                "website_url": website_url
            }
        }
    
    def get_outputs(self) -> Dict[str, Any]:
        """Get template outputs"""
        if not self.storage_account: return {}
        website_url = self.storage_account.primary_endpoints.apply(
            lambda e: e.web if e and hasattr(e, 'web') else None
        )
        return {
            "website_name": self.name,
            "resource_group": self.resource_group.name if self.resource_group else None,
            "storage_account_name": self.storage_account.name,
            "website_url": website_url
        }
    
    @classmethod
    def get_metadata(cls) -> Dict[str, Any]:
        """Template metadata (Pattern B)"""
        return {
            "name": "azure-static-website",
            "title": "Demo Static Website",
            "description": "Deploy an Archie-branded congratulations page on Azure Storage - perfect for your first Azure deployment!",
            "category": "website",
            "cloud": "azure",
            "version": "1.1.0",
            "author": "InnovativeApps",
            "tags": ["azure", "storage", "website", "static", "free"],
            "base_cost": "$0.00/month",
            "complexity": "low",
            "deployment_time": "3-5 minutes",
            "marketplace_group": "WEBSITES"
        }
    
    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        """Get configuration schema"""
        return {
            "type": "object",
            "properties": {
                "websiteName": {
                    "type": "string",
                    "title": "Website Name",
                    "default": "my-azure-site"
                },
                "resourceGroup": {
                    "type": "string",
                    "title": "Resource Group"
                },
                "location": {
                    "type": "string",
                    "title": "Azure Region",
                    "default": "eastus"
                }
            },
            "required": ["websiteName", "resourceGroup"]
        }
