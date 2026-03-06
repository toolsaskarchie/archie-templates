"""
Azure Helper Functions - Resource Tagging

Provides consistent tagging strategies for all Azure resources.
Azure uses "tags" (key-value pairs) similar to AWS.
"""

from typing import Dict, Optional


def get_standard_tags(
    project: str,
    environment: str,
    managed_by: str = "archie",
    **additional_tags
) -> Dict[str, str]:
    """
    Get standard Azure tags applied to all resources
    
    Args:
        project: Project name
        environment: Environment (dev, test, staging, prod)
        managed_by: Management tool (default: archie)
        **additional_tags: Any additional custom tags
    
    Returns:
        Dict[str, str]: Standard tags dictionary
    
    Example:
        >>> get_standard_tags("myapp", "prod", owner="platform-team")
        {
            'Project': 'myapp',
            'Environment': 'prod',
            'ManagedBy': 'archie',
            'owner': 'platform-team'
        }
    """
    tags = {
        "Project": project,
        "Environment": environment,
        "ManagedBy": managed_by,
    }
    
    # Add any additional tags
    tags.update(additional_tags)
    
    return tags


def get_storage_account_tags(
    project: str,
    environment: str,
    purpose: str = "general",
    **additional_tags
) -> Dict[str, str]:
    """
    Get tags for Azure Storage Account
    
    Args:
        project: Project name
        environment: Environment
        purpose: Storage purpose (static-website, data, backup, logs)
        **additional_tags: Any additional custom tags
    
    Returns:
        Dict[str, str]: Storage account tags
    
    Example:
        >>> get_storage_account_tags("myapp", "prod", "static-website")
        {
            'Project': 'myapp',
            'Environment': 'prod',
            'ManagedBy': 'archie',
            'ResourceType': 'storage-account',
            'Purpose': 'static-website'
        }
    """
    tags = get_standard_tags(project, environment, **additional_tags)
    tags.update({
        "ResourceType": "storage-account",
        "Purpose": purpose
    })
    return tags


def get_resource_group_tags(
    project: str,
    environment: str,
    purpose: str = "general",
    **additional_tags
) -> Dict[str, str]:
    """
    Get tags for Azure Resource Group
    
    Args:
        project: Project name
        environment: Environment
        purpose: Resource group purpose
        **additional_tags: Any additional custom tags
    
    Returns:
        Dict[str, str]: Resource group tags
    """
    tags = get_standard_tags(project, environment, **additional_tags)
    tags.update({
        "ResourceType": "resource-group",
        "Purpose": purpose
    })
    return tags


def get_vm_tags(
    project: str,
    environment: str,
    role: str,
    os_type: str = "linux",
    **additional_tags
) -> Dict[str, str]:
    """
    Get tags for Azure VM
    
    Args:
        project: Project name
        environment: Environment
        role: VM role (web, app, db, etc.)
        os_type: Operating system (linux, windows)
        **additional_tags: Any additional custom tags
    
    Returns:
        Dict[str, str]: VM tags
    """
    tags = get_standard_tags(project, environment, **additional_tags)
    tags.update({
        "ResourceType": "virtual-machine",
        "Role": role,
        "OSType": os_type
    })
    return tags


def get_vnet_tags(
    project: str,
    environment: str,
    network_type: str = "general",
    **additional_tags
) -> Dict[str, str]:
    """
    Get tags for Azure Virtual Network
    
    Args:
        project: Project name
        environment: Environment
        network_type: Network type (general, isolated, hub, spoke)
        **additional_tags: Any additional custom tags
    
    Returns:
        Dict[str, str]: VNet tags
    """
    tags = get_standard_tags(project, environment, **additional_tags)
    tags.update({
        "ResourceType": "virtual-network",
        "NetworkType": network_type
    })
    return tags


def get_subnet_tags(
    project: str,
    environment: str,
    tier: str,
    **additional_tags
) -> Dict[str, str]:
    """
    Get tags for Azure Subnet
    
    Args:
        project: Project name
        environment: Environment
        tier: Subnet tier (public, private, database)
        **additional_tags: Any additional custom tags
    
    Returns:
        Dict[str, str]: Subnet tags
    """
    tags = get_standard_tags(project, environment, **additional_tags)
    tags.update({
        "ResourceType": "subnet",
        "Tier": tier
    })
    return tags


def get_nsg_tags(
    project: str,
    environment: str,
    tier: str = "",
    **additional_tags
) -> Dict[str, str]:
    """
    Get tags for Azure Network Security Group
    
    Args:
        project: Project name
        environment: Environment
        tier: Optional tier (public, private, etc.)
        **additional_tags: Any additional custom tags
    
    Returns:
        Dict[str, str]: NSG tags
    """
    tags = get_standard_tags(project, environment, **additional_tags)
    tags.update({
        "ResourceType": "network-security-group"
    })
    if tier:
        tags["Tier"] = tier
    return tags


def get_sql_server_tags(
    project: str,
    environment: str,
    purpose: str = "general",
    **additional_tags
) -> Dict[str, str]:
    """
    Get tags for Azure SQL Server
    
    Args:
        project: Project name
        environment: Environment
        purpose: SQL Server purpose
        **additional_tags: Any additional custom tags
    
    Returns:
        Dict[str, str]: SQL Server tags
    """
    tags = get_standard_tags(project, environment, **additional_tags)
    tags.update({
        "ResourceType": "sql-server",
        "Purpose": purpose
    })
    return tags


def get_app_service_tags(
    project: str,
    environment: str,
    app_type: str = "web",
    **additional_tags
) -> Dict[str, str]:
    """
    Get tags for Azure App Service
    
    Args:
        project: Project name
        environment: Environment
        app_type: App type (web, api, function)
        **additional_tags: Any additional custom tags
    
    Returns:
        Dict[str, str]: App Service tags
    """
    tags = get_standard_tags(project, environment, **additional_tags)
    tags.update({
        "ResourceType": "app-service",
        "AppType": app_type
    })
    return tags


def get_key_vault_tags(
    project: str,
    environment: str,
    purpose: str = "secrets",
    **additional_tags
) -> Dict[str, str]:
    """
    Get tags for Azure Key Vault
    
    Args:
        project: Project name
        environment: Environment
        purpose: Key Vault purpose (secrets, keys, certificates)
        **additional_tags: Any additional custom tags
    
    Returns:
        Dict[str, str]: Key Vault tags
    """
    tags = get_standard_tags(project, environment, **additional_tags)
    tags.update({
        "ResourceType": "key-vault",
        "Purpose": purpose
    })
    return tags


def get_aks_cluster_tags(
    project: str,
    environment: str,
    cluster_type: str = "general",
    **additional_tags
) -> Dict[str, str]:
    """
    Get tags for Azure Kubernetes Service cluster
    
    Args:
        project: Project name
        environment: Environment
        cluster_type: Cluster type (general, microservices, ml)
        **additional_tags: Any additional custom tags
    
    Returns:
        Dict[str, str]: AKS cluster tags
    """
    tags = get_standard_tags(project, environment, **additional_tags)
    tags.update({
        "ResourceType": "aks-cluster",
        "ClusterType": cluster_type
    })
    return tags


def get_cosmos_db_tags(
    project: str,
    environment: str,
    api_type: str = "sql",
    **additional_tags
) -> Dict[str, str]:
    """
    Get tags for Azure Cosmos DB account
    
    Args:
        project: Project name
        environment: Environment
        api_type: API type (sql, mongodb, cassandra, gremlin, table)
        **additional_tags: Any additional custom tags
    
    Returns:
        Dict[str, str]: Cosmos DB tags
    """
    tags = get_standard_tags(project, environment, **additional_tags)
    tags.update({
        "ResourceType": "cosmos-db",
        "APIType": api_type
    })
    return tags
