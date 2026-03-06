"""
GCP Helper Functions - Resource Labels

Provides consistent labeling strategies for all GCP resources.
GCP uses "labels" (key-value pairs) instead of "tags".

Label constraints:
- Keys and values can contain lowercase letters, numbers, hyphens, underscores
- Keys must start with lowercase letter
- Max 64 labels per resource
"""

from typing import Dict, Optional


def get_standard_labels(
    project: str,
    environment: str,
    managed_by: str = "archie",
    **additional_labels
) -> Dict[str, str]:
    """
    Get standard GCP labels applied to all resources
    
    Args:
        project: Project name
        environment: Environment (dev, test, staging, prod)
        managed_by: Management tool (default: archie)
        **additional_labels: Any additional custom labels
    
    Returns:
        Dict[str, str]: Standard labels dictionary
    
    Example:
        >>> get_standard_labels("myapp", "prod", owner="platform-team")
        {
            'project': 'myapp',
            'environment': 'prod',
            'managed_by': 'archie',
            'owner': 'platform-team'
        }
    """
    labels = {
        "project": project.lower().replace("_", "-"),
        "environment": environment.lower(),
        "managed_by": managed_by.lower(),
    }
    
    # Add any additional labels (ensure keys are lowercase)
    for key, value in additional_labels.items():
        labels[key.lower().replace("_", "-")] = str(value).lower().replace("_", "-")
    
    return labels


def get_bucket_labels(
    project: str,
    environment: str,
    purpose: str = "general",
    **additional_labels
) -> Dict[str, str]:
    """
    Get labels for GCP Storage Bucket
    
    Args:
        project: Project name
        environment: Environment
        purpose: Bucket purpose (static-website, data, backup, logs)
        **additional_labels: Any additional custom labels
    
    Returns:
        Dict[str, str]: Bucket labels
    
    Example:
        >>> get_bucket_labels("myapp", "prod", "static-website")
        {
            'project': 'myapp',
            'environment': 'prod',
            'managed_by': 'archie',
            'resource_type': 'storage-bucket',
            'purpose': 'static-website'
        }
    """
    labels = get_standard_labels(project, environment, **additional_labels)
    labels.update({
        "resource_type": "storage-bucket",
        "purpose": purpose.lower().replace("_", "-")
    })
    return labels


def get_instance_labels(
    project: str,
    environment: str,
    role: str,
    os_type: str = "linux",
    **additional_labels
) -> Dict[str, str]:
    """
    Get labels for GCP Compute Engine instance
    
    Args:
        project: Project name
        environment: Environment
        role: Instance role (web, app, db, etc.)
        os_type: Operating system (linux, windows)
        **additional_labels: Any additional custom labels
    
    Returns:
        Dict[str, str]: Instance labels
    """
    labels = get_standard_labels(project, environment, **additional_labels)
    labels.update({
        "resource_type": "compute-instance",
        "role": role.lower().replace("_", "-"),
        "os_type": os_type.lower()
    })
    return labels


def get_vpc_labels(
    project: str,
    environment: str,
    network_type: str = "general",
    **additional_labels
) -> Dict[str, str]:
    """
    Get labels for GCP VPC network
    
    Args:
        project: Project name
        environment: Environment
        network_type: Network type (general, isolated, shared)
        **additional_labels: Any additional custom labels
    
    Returns:
        Dict[str, str]: VPC labels
    """
    labels = get_standard_labels(project, environment, **additional_labels)
    labels.update({
        "resource_type": "vpc-network",
        "network_type": network_type.lower().replace("_", "-")
    })
    return labels


def get_subnet_labels(
    project: str,
    environment: str,
    tier: str,
    **additional_labels
) -> Dict[str, str]:
    """
    Get labels for GCP Subnet
    
    Args:
        project: Project name
        environment: Environment
        tier: Subnet tier (public, private, database)
        **additional_labels: Any additional custom labels
    
    Returns:
        Dict[str, str]: Subnet labels
    """
    labels = get_standard_labels(project, environment, **additional_labels)
    labels.update({
        "resource_type": "subnet",
        "tier": tier.lower().replace("_", "-")
    })
    return labels


def get_cloud_sql_labels(
    project: str,
    environment: str,
    db_type: str = "postgres",
    purpose: str = "general",
    **additional_labels
) -> Dict[str, str]:
    """
    Get labels for GCP Cloud SQL instance
    
    Args:
        project: Project name
        environment: Environment
        db_type: Database type (postgres, mysql)
        purpose: SQL instance purpose
        **additional_labels: Any additional custom labels
    
    Returns:
        Dict[str, str]: Cloud SQL labels
    """
    labels = get_standard_labels(project, environment, **additional_labels)
    labels.update({
        "resource_type": "cloud-sql",
        "db_type": db_type.lower(),
        "purpose": purpose.lower().replace("_", "-")
    })
    return labels


def get_cloud_run_labels(
    project: str,
    environment: str,
    service_type: str = "api",
    **additional_labels
) -> Dict[str, str]:
    """
    Get labels for GCP Cloud Run service
    
    Args:
        project: Project name
        environment: Environment
        service_type: Service type (api, web, worker)
        **additional_labels: Any additional custom labels
    
    Returns:
        Dict[str, str]: Cloud Run labels
    """
    labels = get_standard_labels(project, environment, **additional_labels)
    labels.update({
        "resource_type": "cloud-run",
        "service_type": service_type.lower().replace("_", "-")
    })
    return labels


def get_gke_cluster_labels(
    project: str,
    environment: str,
    cluster_type: str = "general",
    **additional_labels
) -> Dict[str, str]:
    """
    Get labels for GCP GKE cluster
    
    Args:
        project: Project name
        environment: Environment
        cluster_type: Cluster type (general, microservices, ml)
        **additional_labels: Any additional custom labels
    
    Returns:
        Dict[str, str]: GKE cluster labels
    """
    labels = get_standard_labels(project, environment, **additional_labels)
    labels.update({
        "resource_type": "gke-cluster",
        "cluster_type": cluster_type.lower().replace("_", "-")
    })
    return labels


def get_cloud_function_labels(
    project: str,
    environment: str,
    function_type: str = "general",
    **additional_labels
) -> Dict[str, str]:
    """
    Get labels for GCP Cloud Function
    
    Args:
        project: Project name
        environment: Environment
        function_type: Function type (http, event, pubsub)
        **additional_labels: Any additional custom labels
    
    Returns:
        Dict[str, str]: Cloud Function labels
    """
    labels = get_standard_labels(project, environment, **additional_labels)
    labels.update({
        "resource_type": "cloud-function",
        "function_type": function_type.lower().replace("_", "-")
    })
    return labels


def get_pubsub_topic_labels(
    project: str,
    environment: str,
    purpose: str = "general",
    **additional_labels
) -> Dict[str, str]:
    """
    Get labels for GCP Pub/Sub topic
    
    Args:
        project: Project name
        environment: Environment
        purpose: Topic purpose (events, notifications, logs)
        **additional_labels: Any additional custom labels
    
    Returns:
        Dict[str, str]: Pub/Sub topic labels
    """
    labels = get_standard_labels(project, environment, **additional_labels)
    labels.update({
        "resource_type": "pubsub-topic",
        "purpose": purpose.lower().replace("_", "-")
    })
    return labels


def get_load_balancer_labels(
    project: str,
    environment: str,
    lb_type: str = "http",
    **additional_labels
) -> Dict[str, str]:
    """
    Get labels for GCP Load Balancer
    
    Args:
        project: Project name
        environment: Environment
        lb_type: Load balancer type (http, tcp, internal)
        **additional_labels: Any additional custom labels
    
    Returns:
        Dict[str, str]: Load balancer labels
    """
    labels = get_standard_labels(project, environment, **additional_labels)
    labels.update({
        "resource_type": "load-balancer",
        "lb_type": lb_type.lower().replace("_", "-")
    })
    return labels


def get_cloud_armor_labels(
    project: str,
    environment: str,
    policy_type: str = "waf",
    **additional_labels
) -> Dict[str, str]:
    """
    Get labels for GCP Cloud Armor security policy
    
    Args:
        project: Project name
        environment: Environment
        policy_type: Policy type (waf, ddos, rate-limiting)
        **additional_labels: Any additional custom labels
    
    Returns:
        Dict[str, str]: Cloud Armor labels
    """
    labels = get_standard_labels(project, environment, **additional_labels)
    labels.update({
        "resource_type": "cloud-armor",
        "policy_type": policy_type.lower().replace("_", "-")
    })
    return labels


def get_cloud_cdn_labels(
    project: str,
    environment: str,
    **additional_labels
) -> Dict[str, str]:
    """
    Get labels for GCP Cloud CDN backend service
    
    Args:
        project: Project name
        environment: Environment
        **additional_labels: Any additional custom labels
    
    Returns:
        Dict[str, str]: Cloud CDN labels
    """
    labels = get_standard_labels(project, environment, **additional_labels)
    labels.update({
        "resource_type": "cloud-cdn"
    })
    return labels
