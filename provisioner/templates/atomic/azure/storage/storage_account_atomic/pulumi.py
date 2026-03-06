"""Azure Storage Account Template

TODO: Refactor to use StorageAccountComponent once it's created.
Component should be located at: provisioner/components/azure/storage/storage_account_component.py
"""
from typing import Dict, Any, Optional
import pulumi
import pulumi_azure_native as azure

from provisioner.templates.atomic.base import AtomicTemplate


class AzureStorageAccountAtomicTemplate(AtomicTemplate):
    """Azure Storage Account Template
    
    Creates an Azure Storage Account.
    
    Creates:
        - azure.storage.StorageAccount
    
    Outputs:
        - storage_account_name: Storage account name
        - primary_endpoints: Primary endpoints
    """
    
    def __init__(self, name: str, config: Dict[str, Any], **kwargs):
        """Initialize Azure Storage Account atomic template"""
        super().__init__(name, config, **kwargs)
        self.account_name = config.get('account_name')
        self.resource_group_name = config.get('resource_group_name')
        self.location = config.get('location')
        self.sku = config.get('sku', {'name': 'Standard_LRS'})
        self.kind = config.get('kind', 'StorageV2')
        self.enable_https_traffic_only = config.get('enable_https_traffic_only', True)
        self.tags = config.get('tags', {})
        self.storage_account: Optional[azure.storage.StorageAccount] = None
    
    def create_infrastructure(self) -> Dict[str, Any]:
        """Create Azure Storage Account"""
        self.storage_account = azure.storage.StorageAccount(
            f"{self.name}-storage-account",
            account_name=self.account_name,
            resource_group_name=self.resource_group_name,
            location=self.location,
            sku=self.sku,
            kind=self.kind,
            enable_https_traffic_only=self.enable_https_traffic_only,
            tags=self.tags,
            opts=self.resource_options
        )
        
        pulumi.export(f"{self.name}_storage_account_name", self.storage_account.name)
        pulumi.export(f"{self.name}_primary_endpoints", self.storage_account.primary_endpoints)
        
        return self.get_outputs()
    
    def get_outputs(self) -> Dict[str, Any]:
        """Get Storage Account outputs"""
        if not self.storage_account:
            raise RuntimeError(f"Storage account {self.name} not created")
        
        return {
            "storage_account_name": self.storage_account.name,
            "primary_endpoints": self.storage_account.primary_endpoints,
            "id": self.storage_account.id,
        }
