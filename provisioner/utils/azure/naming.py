"""
Azure Helper Functions - Resource Naming Conventions

Provides consistent naming patterns for all Azure resources.
Azure naming rules: lowercase, alphanumeric, hyphens (resource-specific limits)
"""

from typing import Optional


def get_resource_name(
    project: str,
    environment: str,
    resource_type: str,
    suffix: str = ""
) -> str:
    """
    Generate consistent resource name following pattern: project-environment-resourcetype[-suffix]
    
    Args:
        project: Project name
        environment: Environment (dev, test, staging, prod)
        resource_type: Type of resource (storage, vm, sql, etc.)
        suffix: Optional suffix (region, index, purpose)
    
    Returns:
        str: Resource name (lowercase, hyphens)
    
    Example:
        >>> get_resource_name("myapp", "prod", "storage")
        "myapp-prod-storage"
        >>> get_resource_name("myapp", "prod", "storage", "eastus")
        "myapp-prod-storage-eastus"
    """
    parts = [project, environment, resource_type]
    if suffix:
        parts.append(suffix)
    return "-".join(parts).lower()


def get_storage_account_name(
    project: str,
    environment: str,
    region: str = ""
) -> str:
    """
    Get Azure Storage Account name
    
    Azure storage account naming rules:
    - 3-24 characters
    - Lowercase letters and numbers only (no hyphens!)
    - Globally unique
    
    Args:
        project: Project name
        environment: Environment
        region: Optional region for uniqueness
    
    Returns:
        str: Storage account name (lowercase alphanumeric only)
    
    Example:
        >>> get_storage_account_name("myapp", "prod", "eastus")
        "myappprodeastus"
    """
    parts = [project, environment]
    if region:
        # Remove hyphens from region (e.g., east-us → eastus)
        parts.append(region.replace("-", ""))
    
    name = "".join(parts).lower().replace("-", "")
    
    # Ensure it's not too long (max 24 chars)
    if len(name) > 24:
        name = name[:24]
    
    # Ensure it's at least 3 chars
    if len(name) < 3:
        name = name + "001"
    
    return name


def get_resource_group_name(
    project: str,
    environment: str,
    region: str = ""
) -> str:
    """
    Get Azure Resource Group name
    
    Args:
        project: Project name
        environment: Environment
        region: Optional region
    
    Returns:
        str: Resource group name
    
    Example:
        >>> get_resource_group_name("myapp", "prod", "eastus")
        "myapp-prod-eastus-rg"
    """
    if region:
        return f"{project}-{environment}-{region}-rg".lower()
    return f"{project}-{environment}-rg".lower()


def get_container_name(
    purpose: str
) -> str:
    """
    Get Azure Storage Container name
    
    Azure container naming rules:
    - 3-63 characters
    - Lowercase letters, numbers, hyphens
    - Must start with letter or number
    
    Args:
        purpose: Container purpose (web, data, backup, etc.)
    
    Returns:
        str: Container name
    
    Example:
        >>> get_container_name("web")
        "web"
        >>> get_container_name("static-assets")
        "static-assets"
    """
    return purpose.lower()


def get_vm_name(
    project: str,
    environment: str,
    purpose: str = "vm"
) -> str:
    """
    Get Azure VM name
    
    Args:
        project: Project name
        environment: Environment
        purpose: VM purpose (web, app, db, etc.)
    
    Returns:
        str: VM name
    """
    return get_resource_name(project, environment, purpose)


def get_vnet_name(
    project: str,
    environment: str
) -> str:
    """
    Get Azure Virtual Network name
    
    Args:
        project: Project name
        environment: Environment
    
    Returns:
        str: VNet name
    """
    return get_resource_name(project, environment, "vnet")


def get_subnet_name(
    project: str,
    environment: str,
    tier: str
) -> str:
    """
    Get Azure Subnet name
    
    Args:
        project: Project name
        environment: Environment
        tier: Subnet tier (public, private, database)
    
    Returns:
        str: Subnet name
    """
    return get_resource_name(project, environment, f"{tier}-subnet")


def get_nsg_name(
    project: str,
    environment: str,
    tier: str = ""
) -> str:
    """
    Get Azure Network Security Group name
    
    Args:
        project: Project name
        environment: Environment
        tier: Optional tier (public, private, etc.)
    
    Returns:
        str: NSG name
    """
    if tier:
        return get_resource_name(project, environment, f"{tier}-nsg")
    return get_resource_name(project, environment, "nsg")


def get_sql_server_name(
    project: str,
    environment: str,
    region: str = ""
) -> str:
    """
    Get Azure SQL Server name (must be globally unique)
    
    Args:
        project: Project name
        environment: Environment
        region: Optional region for uniqueness
    
    Returns:
        str: SQL Server name
    """
    if region:
        return get_resource_name(project, environment, "sql", region)
    return get_resource_name(project, environment, "sql")


def get_app_service_plan_name(
    project: str,
    environment: str
) -> str:
    """
    Get Azure App Service Plan name
    
    Args:
        project: Project name
        environment: Environment
    
    Returns:
        str: App Service Plan name
    """
    return get_resource_name(project, environment, "asp")


def get_app_service_name(
    project: str,
    environment: str,
    app_name: str = ""
) -> str:
    """
    Get Azure App Service name (must be globally unique)
    
    Args:
        project: Project name
        environment: Environment
        app_name: Optional app name
    
    Returns:
        str: App Service name
    """
    if app_name:
        return get_resource_name(project, environment, app_name)
    return get_resource_name(project, environment, "app")


def get_key_vault_name(
    project: str,
    environment: str
) -> str:
    """
    Get Azure Key Vault name
    
    Azure Key Vault naming rules:
    - 3-24 characters
    - Alphanumeric and hyphens
    - Must start with letter
    - Globally unique
    
    Args:
        project: Project name
        environment: Environment
    
    Returns:
        str: Key Vault name
    """
    name = get_resource_name(project, environment, "kv")
    
    # Ensure it's not too long (max 24 chars)
    if len(name) > 24:
        name = name[:24]
    
    return name


def get_aks_cluster_name(
    project: str,
    environment: str
) -> str:
    """
    Get Azure Kubernetes Service cluster name
    
    Args:
        project: Project name
        environment: Environment
    
    Returns:
        str: AKS cluster name
    """
    return get_resource_name(project, environment, "aks")


def get_cosmos_db_account_name(
    project: str,
    environment: str
) -> str:
    """
    Get Azure Cosmos DB account name (must be globally unique)
    
    Args:
        project: Project name
        environment: Environment
    
    Returns:
        str: Cosmos DB account name
    """
    return get_resource_name(project, environment, "cosmos")
