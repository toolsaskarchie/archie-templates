"""
Azure Helper Functions - Smart Defaults and Resource Configuration

Provides intelligent defaults and auto-generation for Azure resources.
"""

from typing import Dict, List, Optional, Any


def get_smart_storage_account_config(
    project: str,
    environment: str,
    region: str = "eastus",
    enable_static_website: bool = False,
    **overrides
) -> Dict[str, Any]:
    """
    Get smart configuration for Azure Storage Account
    
    Args:
        project: Project name
        environment: Environment
        region: Azure region (default: eastus)
        enable_static_website: Enable static website hosting
        **overrides: Override any default settings
    
    Returns:
        Dict with storage account configuration
    
    Example:
        >>> get_smart_storage_account_config("myapp", "prod", enable_static_website=True)
        {
            'account_tier': 'Standard',
            'account_replication_type': 'LRS',
            'enable_https_traffic_only': True,
            'min_tls_version': 'TLS1_2',
            'allow_blob_public_access': True,
            'static_website': {...}
        }
    """
    # Base configuration
    config = {
        "account_tier": "Standard",
        "account_replication_type": "LRS" if environment in ["dev", "test"] else "GRS",
        "enable_https_traffic_only": True,
        "min_tls_version": "TLS1_2",
        "allow_blob_public_access": enable_static_website,
    }
    
    # Add static website config if enabled
    if enable_static_website:
        config["static_website"] = {
            "index_document": "index.html",
            "error_404_document": "404.html"
        }
    
    # Apply overrides
    config.update(overrides)
    
    return config


def get_smart_resource_group_config(
    project: str,
    environment: str,
    region: str = "eastus",
    **overrides
) -> Dict[str, Any]:
    """
    Get smart configuration for Azure Resource Group
    
    Args:
        project: Project name
        environment: Environment
        region: Azure region (default: eastus)
        **overrides: Override any default settings
    
    Returns:
        Dict with resource group configuration
    """
    config = {
        "location": region
    }
    
    config.update(overrides)
    return config


def get_smart_vm_config(
    project: str,
    environment: str,
    vm_size: str = "",
    os_type: str = "linux",
    **overrides
) -> Dict[str, Any]:
    """
    Get smart configuration for Azure VM
    
    Args:
        project: Project name
        environment: Environment
        vm_size: VM size (auto-selected if not provided)
        os_type: Operating system (linux, windows)
        **overrides: Override any default settings
    
    Returns:
        Dict with VM configuration
    """
    # Auto-select VM size based on environment
    if not vm_size:
        vm_size_map = {
            "dev": "Standard_B2s",      # 2 vCPU, 4 GB RAM - cost-effective
            "test": "Standard_B2s",     # 2 vCPU, 4 GB RAM
            "staging": "Standard_D2s_v3",  # 2 vCPU, 8 GB RAM
            "prod": "Standard_D4s_v3"   # 4 vCPU, 16 GB RAM
        }
        vm_size = vm_size_map.get(environment, "Standard_B2s")
    
    config = {
        "size": vm_size,
        "delete_os_disk_on_termination": True,
        "delete_data_disks_on_termination": True,
    }
    
    # Linux-specific settings
    if os_type == "linux":
        config["storage_os_disk"] = {
            "caching": "ReadWrite",
            "create_option": "FromImage",
            "managed_disk_type": "Premium_LRS" if environment == "prod" else "Standard_LRS"
        }
    
    config.update(overrides)
    return config


def get_smart_vnet_config(
    project: str,
    environment: str,
    region: str = "eastus",
    address_space: Optional[List[str]] = None,
    **overrides
) -> Dict[str, Any]:
    """
    Get smart configuration for Azure Virtual Network
    
    Args:
        project: Project name
        environment: Environment
        region: Azure region
        address_space: CIDR blocks (auto-generated if not provided)
        **overrides: Override any default settings
    
    Returns:
        Dict with VNet configuration
    """
    # Auto-generate address space if not provided
    if not address_space:
        # Use different CIDR ranges per environment to avoid conflicts
        cidr_map = {
            "dev": ["10.0.0.0/16"],
            "test": ["10.1.0.0/16"],
            "staging": ["10.2.0.0/16"],
            "prod": ["10.3.0.0/16"]
        }
        address_space = cidr_map.get(environment, ["10.0.0.0/16"])
    
    config = {
        "location": region,
        "address_space": address_space
    }
    
    config.update(overrides)
    return config


def get_smart_subnet_config(
    vnet_address_space: str,
    tier: str,
    **overrides
) -> Dict[str, Any]:
    """
    Get smart configuration for Azure Subnet
    
    Args:
        vnet_address_space: Parent VNet CIDR (e.g., "10.0.0.0/16")
        tier: Subnet tier (public, private, database)
        **overrides: Override any default settings
    
    Returns:
        Dict with subnet configuration
    """
    # Auto-generate subnet CIDR based on tier
    # Assumes VNet is /16, creates /24 subnets
    base = vnet_address_space.split('/')[0]
    octets = base.split('.')
    
    tier_map = {
        "public": f"{octets[0]}.{octets[1]}.0.0/24",
        "private": f"{octets[0]}.{octets[1]}.1.0/24",
        "database": f"{octets[0]}.{octets[1]}.2.0/24"
    }
    
    config = {
        "address_prefixes": [tier_map.get(tier, f"{octets[0]}.{octets[1]}.0.0/24")]
    }
    
    config.update(overrides)
    return config


def get_smart_sql_server_config(
    project: str,
    environment: str,
    region: str = "eastus",
    **overrides
) -> Dict[str, Any]:
    """
    Get smart configuration for Azure SQL Server
    
    Args:
        project: Project name
        environment: Environment
        region: Azure region
        **overrides: Override any default settings
    
    Returns:
        Dict with SQL Server configuration
    """
    config = {
        "location": region,
        "version": "12.0",
        "minimum_tls_version": "1.2"
    }
    
    config.update(overrides)
    return config


def get_smart_app_service_plan_config(
    project: str,
    environment: str,
    region: str = "eastus",
    **overrides
) -> Dict[str, Any]:
    """
    Get smart configuration for Azure App Service Plan
    
    Args:
        project: Project name
        environment: Environment
        region: Azure region
        **overrides: Override any default settings
    
    Returns:
        Dict with App Service Plan configuration
    """
    # Auto-select SKU based on environment
    sku_map = {
        "dev": {"tier": "Free", "size": "F1"},
        "test": {"tier": "Basic", "size": "B1"},
        "staging": {"tier": "Standard", "size": "S1"},
        "prod": {"tier": "Premium", "size": "P1v2"}
    }
    
    config = {
        "location": region,
        "kind": "Linux",
        "reserved": True,  # Required for Linux
        "sku": sku_map.get(environment, {"tier": "Basic", "size": "B1"})
    }
    
    config.update(overrides)
    return config


def get_smart_key_vault_config(
    project: str,
    environment: str,
    region: str = "eastus",
    **overrides
) -> Dict[str, Any]:
    """
    Get smart configuration for Azure Key Vault
    
    Args:
        project: Project name
        environment: Environment
        region: Azure region
        **overrides: Override any default settings
    
    Returns:
        Dict with Key Vault configuration
    """
    config = {
        "location": region,
        "sku_name": "standard",
        "enabled_for_deployment": False,
        "enabled_for_disk_encryption": False,
        "enabled_for_template_deployment": True,
        "enable_rbac_authorization": True,
        "purge_protection_enabled": environment == "prod",
        "soft_delete_retention_days": 90 if environment == "prod" else 7
    }
    
    config.update(overrides)
    return config


def get_smart_aks_cluster_config(
    project: str,
    environment: str,
    region: str = "eastus",
    **overrides
) -> Dict[str, Any]:
    """
    Get smart configuration for Azure Kubernetes Service cluster
    
    Args:
        project: Project name
        environment: Environment
        region: Azure region
        **overrides: Override any default settings
    
    Returns:
        Dict with AKS cluster configuration
    """
    # Auto-select node count and VM size based on environment
    node_config = {
        "dev": {"count": 1, "vm_size": "Standard_D2s_v3"},
        "test": {"count": 2, "vm_size": "Standard_D2s_v3"},
        "staging": {"count": 2, "vm_size": "Standard_D4s_v3"},
        "prod": {"count": 3, "vm_size": "Standard_D4s_v3"}
    }
    
    config = {
        "location": region,
        "dns_prefix": f"{project}-{environment}",
        "kubernetes_version": "1.27",
        "default_node_pool": {
            "name": "default",
            "node_count": node_config.get(environment, {"count": 2})["count"],
            "vm_size": node_config.get(environment, {"vm_size": "Standard_D2s_v3"})["vm_size"],
            "enable_auto_scaling": environment in ["staging", "prod"],
            "min_count": 1 if environment in ["staging", "prod"] else None,
            "max_count": 5 if environment in ["staging", "prod"] else None
        },
        "network_profile": {
            "network_plugin": "azure",
            "load_balancer_sku": "standard"
        }
    }
    
    config.update(overrides)
    return config


def get_azure_region_choices() -> List[Dict[str, str]]:
    """
    Get list of common Azure regions
    
    Returns:
        List of dicts with value and label for each region
    """
    return [
        {"value": "eastus", "label": "East US"},
        {"value": "eastus2", "label": "East US 2"},
        {"value": "westus", "label": "West US"},
        {"value": "westus2", "label": "West US 2"},
        {"value": "centralus", "label": "Central US"},
        {"value": "northcentralus", "label": "North Central US"},
        {"value": "southcentralus", "label": "South Central US"},
        {"value": "westcentralus", "label": "West Central US"},
        {"value": "canadacentral", "label": "Canada Central"},
        {"value": "canadaeast", "label": "Canada East"},
        {"value": "brazilsouth", "label": "Brazil South"},
        {"value": "northeurope", "label": "North Europe"},
        {"value": "westeurope", "label": "West Europe"},
        {"value": "uksouth", "label": "UK South"},
        {"value": "ukwest", "label": "UK West"},
        {"value": "francecentral", "label": "France Central"},
        {"value": "germanywestcentral", "label": "Germany West Central"},
        {"value": "norwayeast", "label": "Norway East"},
        {"value": "switzerlandnorth", "label": "Switzerland North"},
        {"value": "swedencentral", "label": "Sweden Central"},
        {"value": "southeastasia", "label": "Southeast Asia"},
        {"value": "eastasia", "label": "East Asia"},
        {"value": "australiaeast", "label": "Australia East"},
        {"value": "australiasoutheast", "label": "Australia Southeast"},
        {"value": "japaneast", "label": "Japan East"},
        {"value": "japanwest", "label": "Japan West"},
        {"value": "koreacentral", "label": "Korea Central"},
        {"value": "koreasouth", "label": "Korea South"},
        {"value": "southindia", "label": "South India"},
        {"value": "centralindia", "label": "Central India"},
        {"value": "westindia", "label": "West India"},
        {"value": "uaenorth", "label": "UAE North"}
    ]
