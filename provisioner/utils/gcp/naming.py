"""
GCP Helper Functions - Resource Naming Conventions

Provides consistent naming patterns for all GCP resources.
GCP naming rules: lowercase, alphanumeric, hyphens (resource-specific limits)
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
        resource_type: Type of resource (bucket, instance, sql, etc.)
        suffix: Optional suffix (region, index, purpose)
    
    Returns:
        str: Resource name (lowercase, hyphens)
    
    Example:
        >>> get_resource_name("myapp", "prod", "bucket")
        "myapp-prod-bucket"
        >>> get_resource_name("myapp", "prod", "bucket", "us-east1")
        "myapp-prod-bucket-us-east1"
    """
    parts = [project, environment, resource_type]
    if suffix:
        parts.append(suffix)
    return "-".join(parts).lower()


def get_bucket_name(
    project: str,
    environment: str,
    purpose: str = "",
    region: str = ""
) -> str:
    """
    Get GCP Storage Bucket name
    
    GCP bucket naming rules:
    - 3-63 characters
    - Lowercase letters, numbers, hyphens, underscores, dots
    - Must start and end with number or letter
    - Globally unique
    
    Args:
        project: Project name
        environment: Environment
        purpose: Bucket purpose (static-website, data, backup, etc.)
        region: Optional region for uniqueness
    
    Returns:
        str: Bucket name
    
    Example:
        >>> get_bucket_name("myapp", "prod", "static-website", "us-east1")
        "myapp-prod-static-website-us-east1"
    """
    parts = [project, environment]
    if purpose:
        parts.append(purpose)
    if region:
        parts.append(region)
    
    name = "-".join(parts).lower()
    
    # Ensure it's not too long (max 63 chars)
    if len(name) > 63:
        name = name[:63]
    
    return name


def get_instance_name(
    project: str,
    environment: str,
    purpose: str = "vm",
    zone: str = ""
) -> str:
    """
    Get GCP Compute Engine instance name
    
    Args:
        project: Project name
        environment: Environment
        purpose: Instance purpose (web, app, db, etc.)
        zone: Optional zone suffix
    
    Returns:
        str: Instance name
    
    Example:
        >>> get_instance_name("myapp", "prod", "web", "us-east1-b")
        "myapp-prod-web-us-east1-b"
    """
    if zone:
        return get_resource_name(project, environment, purpose, zone)
    return get_resource_name(project, environment, purpose)


def get_vpc_name(
    project: str,
    environment: str
) -> str:
    """
    Get GCP VPC network name
    
    Args:
        project: Project name
        environment: Environment
    
    Returns:
        str: VPC name
    """
    return get_resource_name(project, environment, "vpc")


def get_subnet_name(
    project: str,
    environment: str,
    tier: str,
    region: str = ""
) -> str:
    """
    Get GCP Subnet name
    
    Args:
        project: Project name
        environment: Environment
        tier: Subnet tier (public, private, database)
        region: Optional region
    
    Returns:
        str: Subnet name
    """
    if region:
        return get_resource_name(project, environment, f"{tier}-subnet", region)
    return get_resource_name(project, environment, f"{tier}-subnet")


def get_firewall_rule_name(
    project: str,
    environment: str,
    purpose: str
) -> str:
    """
    Get GCP Firewall rule name
    
    Args:
        project: Project name
        environment: Environment
        purpose: Rule purpose (allow-http, allow-ssh, etc.)
    
    Returns:
        str: Firewall rule name
    """
    return get_resource_name(project, environment, purpose)


def get_cloud_sql_instance_name(
    project: str,
    environment: str,
    db_type: str = "postgres"
) -> str:
    """
    Get GCP Cloud SQL instance name
    
    Args:
        project: Project name
        environment: Environment
        db_type: Database type (postgres, mysql)
    
    Returns:
        str: Cloud SQL instance name
    """
    return get_resource_name(project, environment, f"{db_type}-db")


def get_cloud_run_service_name(
    project: str,
    environment: str,
    service: str = "api"
) -> str:
    """
    Get GCP Cloud Run service name
    
    Args:
        project: Project name
        environment: Environment
        service: Service name (api, web, worker, etc.)
    
    Returns:
        str: Cloud Run service name
    """
    return get_resource_name(project, environment, service)


def get_gke_cluster_name(
    project: str,
    environment: str,
    region: str = ""
) -> str:
    """
    Get GCP GKE cluster name
    
    Args:
        project: Project name
        environment: Environment
        region: Optional region
    
    Returns:
        str: GKE cluster name
    """
    if region:
        return get_resource_name(project, environment, "gke", region)
    return get_resource_name(project, environment, "gke")


def get_cloud_function_name(
    project: str,
    environment: str,
    function: str
) -> str:
    """
    Get GCP Cloud Function name
    
    Args:
        project: Project name
        environment: Environment
        function: Function name (processor, webhook, etc.)
    
    Returns:
        str: Cloud Function name
    """
    return get_resource_name(project, environment, function)


def get_pubsub_topic_name(
    project: str,
    environment: str,
    topic: str
) -> str:
    """
    Get GCP Pub/Sub topic name
    
    Args:
        project: Project name
        environment: Environment
        topic: Topic name (events, notifications, etc.)
    
    Returns:
        str: Pub/Sub topic name
    """
    return get_resource_name(project, environment, topic)


def get_secret_name(
    project: str,
    environment: str,
    secret: str
) -> str:
    """
    Get GCP Secret Manager secret name
    
    Args:
        project: Project name
        environment: Environment
        secret: Secret name (api-key, db-password, etc.)
    
    Returns:
        str: Secret name
    """
    return get_resource_name(project, environment, secret)


def get_load_balancer_name(
    project: str,
    environment: str,
    purpose: str = "main"
) -> str:
    """
    Get GCP Load Balancer name
    
    Args:
        project: Project name
        environment: Environment
        purpose: Load balancer purpose (main, internal, etc.)
    
    Returns:
        str: Load balancer name
    """
    return get_resource_name(project, environment, f"{purpose}-lb")


def get_service_account_name(
    project: str,
    environment: str,
    service: str
) -> str:
    """
    Get GCP Service Account name
    
    GCP service account naming rules:
    - 6-30 characters
    - Lowercase letters, numbers, hyphens
    - Must start with letter
    
    Args:
        project: Project name
        environment: Environment
        service: Service name (compute, gke, cloud-run, etc.)
    
    Returns:
        str: Service account name
    
    Example:
        >>> get_service_account_name("myapp", "prod", "compute")
        "myapp-prod-compute"
    """
    name = get_resource_name(project, environment, service)
    
    # Ensure it's not too long (max 30 chars)
    if len(name) > 30:
        name = name[:30]
    
    # Ensure it's at least 6 chars
    if len(name) < 6:
        name = name + "-svc"
    
    return name


def get_cloud_armor_policy_name(
    project: str,
    environment: str,
    purpose: str = "waf"
) -> str:
    """
    Get GCP Cloud Armor security policy name
    
    Args:
        project: Project name
        environment: Environment
        purpose: Policy purpose (waf, ddos, etc.)
    
    Returns:
        str: Cloud Armor policy name
    """
    return get_resource_name(project, environment, f"{purpose}-policy")


def get_cloud_cdn_name(
    project: str,
    environment: str
) -> str:
    """
    Get GCP Cloud CDN backend service name
    
    Args:
        project: Project name
        environment: Environment
    
    Returns:
        str: Cloud CDN name
    """
    return get_resource_name(project, environment, "cdn")
