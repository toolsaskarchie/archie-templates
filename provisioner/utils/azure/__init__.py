"""
Azure Utilities Package

Provides helper functions for Azure resource management:
- defaults: Smart defaults and auto-configuration
- tags: Standard tagging strategies
- naming: Resource naming conventions
"""

from .defaults import (
    get_smart_storage_account_config,
    get_smart_resource_group_config,
    get_smart_vm_config,
    get_smart_vnet_config,
    get_smart_subnet_config,
    get_smart_sql_server_config,
    get_smart_app_service_plan_config,
    get_smart_key_vault_config,
    get_smart_aks_cluster_config,
    get_azure_region_choices,
)

from .tags import (
    get_standard_tags,
    get_storage_account_tags,
    get_resource_group_tags,
    get_vm_tags,
    get_vnet_tags,
    get_subnet_tags,
    get_nsg_tags,
    get_sql_server_tags,
    get_app_service_tags,
    get_key_vault_tags,
    get_aks_cluster_tags,
    get_cosmos_db_tags,
)

from .naming import (
    get_resource_name,
    get_storage_account_name,
    get_resource_group_name,
    get_container_name,
    get_vm_name,
    get_vnet_name,
    get_subnet_name,
    get_nsg_name,
    get_sql_server_name,
    get_app_service_plan_name,
    get_app_service_name,
    get_key_vault_name,
    get_aks_cluster_name,
    get_cosmos_db_account_name,
)

__all__ = [
    # defaults
    "get_smart_storage_account_config",
    "get_smart_resource_group_config",
    "get_smart_vm_config",
    "get_smart_vnet_config",
    "get_smart_subnet_config",
    "get_smart_sql_server_config",
    "get_smart_app_service_plan_config",
    "get_smart_key_vault_config",
    "get_smart_aks_cluster_config",
    "get_azure_region_choices",
    # tags
    "get_standard_tags",
    "get_storage_account_tags",
    "get_resource_group_tags",
    "get_vm_tags",
    "get_vnet_tags",
    "get_subnet_tags",
    "get_nsg_tags",
    "get_sql_server_tags",
    "get_app_service_tags",
    "get_key_vault_tags",
    "get_aks_cluster_tags",
    "get_cosmos_db_tags",
    # naming
    "get_resource_name",
    "get_storage_account_name",
    "get_resource_group_name",
    "get_container_name",
    "get_vm_name",
    "get_vnet_name",
    "get_subnet_name",
    "get_nsg_name",
    "get_sql_server_name",
    "get_app_service_plan_name",
    "get_app_service_name",
    "get_key_vault_name",
    "get_aks_cluster_name",
    "get_cosmos_db_account_name",
]
