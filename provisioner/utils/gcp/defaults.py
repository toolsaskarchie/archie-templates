"""
GCP Helper Functions - Smart Defaults and Resource Configuration

Provides intelligent defaults and auto-generation for GCP resources.
"""

from typing import Dict, List, Optional, Any


def get_smart_bucket_config(
    project: str,
    environment: str,
    region: str = "us-east1",
    enable_static_website: bool = False,
    **overrides
) -> Dict[str, Any]:
    """
    Get smart configuration for GCP Storage Bucket
    
    Args:
        project: Project name
        environment: Environment
        region: GCP region (default: us-east1)
        enable_static_website: Enable static website hosting
        **overrides: Override any default settings
    
    Returns:
        Dict with bucket configuration
    
    Example:
        >>> get_smart_bucket_config("myapp", "prod", enable_static_website=True)
        {
            'location': 'us-east1',
            'storage_class': 'STANDARD',
            'uniform_bucket_level_access': True,
            'website': {...}
        }
    """
    # Choose storage class based on environment
    storage_class_map = {
        "dev": "STANDARD",
        "test": "STANDARD",
        "staging": "STANDARD",
        "prod": "MULTI_REGIONAL" if region.startswith("us") else "STANDARD"
    }
    
    config = {
        "location": region,
        "storage_class": storage_class_map.get(environment, "STANDARD"),
        "uniform_bucket_level_access": True,
        "force_destroy": environment in ["dev", "test"],  # Allow easy cleanup in dev/test
    }
    
    # Add static website config if enabled
    if enable_static_website:
        config["website"] = {
            "main_page_suffix": "index.html",
            "not_found_page": "404.html"
        }
    
    # Add versioning for production
    if environment == "prod" and not enable_static_website:
        config["versioning"] = {
            "enabled": True
        }
    
    # Apply overrides
    config.update(overrides)
    
    return config


def get_smart_instance_config(
    project: str,
    environment: str,
    zone: str = "us-east1-b",
    machine_type: str = "",
    os_type: str = "linux",
    **overrides
) -> Dict[str, Any]:
    """
    Get smart configuration for GCP Compute Engine instance
    
    Args:
        project: Project name
        environment: Environment
        zone: GCP zone (default: us-east1-b)
        machine_type: Machine type (auto-selected if not provided)
        os_type: Operating system (linux, windows)
        **overrides: Override any default settings
    
    Returns:
        Dict with instance configuration
    """
    # Auto-select machine type based on environment
    if not machine_type:
        machine_type_map = {
            "dev": "e2-micro",        # 0.25-2 vCPU, 1 GB RAM - free tier eligible
            "test": "e2-small",       # 0.5-2 vCPU, 2 GB RAM
            "staging": "e2-medium",   # 1-2 vCPU, 4 GB RAM
            "prod": "e2-standard-2"   # 2 vCPU, 8 GB RAM
        }
        machine_type = machine_type_map.get(environment, "e2-small")
    
    config = {
        "zone": zone,
        "machine_type": machine_type,
        "deletion_protection": environment == "prod",
        "boot_disk": {
            "initialize_params": {
                "image": "debian-cloud/debian-11" if os_type == "linux" else "windows-cloud/windows-2022",
                "size": 20 if os_type == "linux" else 50,
                "type": "pd-standard" if environment in ["dev", "test"] else "pd-balanced"
            }
        }
    }
    
    config.update(overrides)
    return config


def get_smart_vpc_config(
    project: str,
    environment: str,
    auto_create_subnetworks: bool = False,
    **overrides
) -> Dict[str, Any]:
    """
    Get smart configuration for GCP VPC network
    
    Args:
        project: Project name
        environment: Environment
        auto_create_subnetworks: Auto-create subnets (default: False for custom VPCs)
        **overrides: Override any default settings
    
    Returns:
        Dict with VPC configuration
    """
    config = {
        "auto_create_subnetworks": auto_create_subnetworks,
        "mtu": 1460,  # Default GCP MTU
        "routing_mode": "REGIONAL" if environment in ["dev", "test"] else "GLOBAL"
    }
    
    config.update(overrides)
    return config


def get_smart_subnet_config(
    project: str,
    environment: str,
    region: str,
    tier: str,
    vpc_cidr: str = "10.0.0.0/16",
    **overrides
) -> Dict[str, Any]:
    """
    Get smart configuration for GCP Subnet
    
    Args:
        project: Project name
        environment: Environment
        region: GCP region
        tier: Subnet tier (public, private, database)
        vpc_cidr: Parent VPC CIDR (for auto-generating subnet CIDR)
        **overrides: Override any default settings
    
    Returns:
        Dict with subnet configuration
    """
    # Auto-generate subnet CIDR based on tier
    # Assumes VPC is /16, creates /24 subnets
    base = vpc_cidr.split('/')[0]
    octets = base.split('.')
    
    tier_map = {
        "public": f"{octets[0]}.{octets[1]}.0.0/24",
        "private": f"{octets[0]}.{octets[1]}.1.0/24",
        "database": f"{octets[0]}.{octets[1]}.2.0/24"
    }
    
    config = {
        "region": region,
        "ip_cidr_range": tier_map.get(tier, f"{octets[0]}.{octets[1]}.0.0/24"),
        "private_ip_google_access": tier in ["private", "database"]
    }
    
    config.update(overrides)
    return config


def get_smart_cloud_sql_config(
    project: str,
    environment: str,
    region: str = "us-east1",
    db_type: str = "postgres",
    **overrides
) -> Dict[str, Any]:
    """
    Get smart configuration for GCP Cloud SQL instance
    
    Args:
        project: Project name
        environment: Environment
        region: GCP region
        db_type: Database type (postgres, mysql)
        **overrides: Override any default settings
    
    Returns:
        Dict with Cloud SQL configuration
    """
    # Choose database version
    db_version_map = {
        "postgres": "POSTGRES_15",
        "mysql": "MYSQL_8_0"
    }
    
    # Choose tier based on environment
    tier_map = {
        "dev": "db-f1-micro",         # Shared CPU, 0.6 GB RAM - free tier
        "test": "db-g1-small",        # Shared CPU, 1.7 GB RAM
        "staging": "db-n1-standard-1",  # 1 vCPU, 3.75 GB RAM
        "prod": "db-n1-standard-2"    # 2 vCPU, 7.5 GB RAM
    }
    
    config = {
        "region": region,
        "database_version": db_version_map.get(db_type, "POSTGRES_15"),
        "tier": tier_map.get(environment, "db-g1-small"),
        "deletion_protection": environment == "prod",
        "settings": {
            "availability_type": "REGIONAL" if environment == "prod" else "ZONAL",
            "backup_configuration": {
                "enabled": True,
                "start_time": "03:00",
                "point_in_time_recovery_enabled": environment == "prod"
            },
            "ip_configuration": {
                "ipv4_enabled": True,
                "require_ssl": environment in ["staging", "prod"]
            }
        }
    }
    
    config.update(overrides)
    return config


def get_smart_cloud_run_config(
    project: str,
    environment: str,
    region: str = "us-east1",
    **overrides
) -> Dict[str, Any]:
    """
    Get smart configuration for GCP Cloud Run service
    
    Args:
        project: Project name
        environment: Environment
        region: GCP region
        **overrides: Override any default settings
    
    Returns:
        Dict with Cloud Run configuration
    """
    # Auto-scale configuration based on environment
    autoscaling_map = {
        "dev": {"min_instances": 0, "max_instances": 2},
        "test": {"min_instances": 0, "max_instances": 5},
        "staging": {"min_instances": 1, "max_instances": 10},
        "prod": {"min_instances": 2, "max_instances": 20}
    }
    
    # Resource limits based on environment
    resources_map = {
        "dev": {"cpu": "1", "memory": "512Mi"},
        "test": {"cpu": "1", "memory": "512Mi"},
        "staging": {"cpu": "2", "memory": "1Gi"},
        "prod": {"cpu": "2", "memory": "2Gi"}
    }
    
    config = {
        "location": region,
        "autoscaling": autoscaling_map.get(environment, {"min_instances": 0, "max_instances": 5}),
        "resources": resources_map.get(environment, {"cpu": "1", "memory": "512Mi"}),
        "timeout": "60s" if environment in ["dev", "test"] else "300s"
    }
    
    config.update(overrides)
    return config


def get_smart_gke_cluster_config(
    project: str,
    environment: str,
    region: str = "us-east1",
    **overrides
) -> Dict[str, Any]:
    """
    Get smart configuration for GCP GKE cluster
    
    Args:
        project: Project name
        environment: Environment
        region: GCP region
        **overrides: Override any default settings
    
    Returns:
        Dict with GKE cluster configuration
    """
    # Node pool configuration based on environment
    node_config = {
        "dev": {"machine_type": "e2-medium", "initial_node_count": 1, "min_nodes": 1, "max_nodes": 3},
        "test": {"machine_type": "e2-medium", "initial_node_count": 2, "min_nodes": 1, "max_nodes": 5},
        "staging": {"machine_type": "e2-standard-4", "initial_node_count": 2, "min_nodes": 2, "max_nodes": 8},
        "prod": {"machine_type": "e2-standard-4", "initial_node_count": 3, "min_nodes": 3, "max_nodes": 10}
    }
    
    env_config = node_config.get(environment, node_config["dev"])
    
    config = {
        "location": region,
        "remove_default_node_pool": True,
        "initial_node_count": 1,
        "network_policy": {"enabled": True},
        "addons_config": {
            "http_load_balancing": {"disabled": False},
            "horizontal_pod_autoscaling": {"disabled": False}
        },
        "node_pool": {
            "name": "default-pool",
            "initial_node_count": env_config["initial_node_count"],
            "node_config": {
                "machine_type": env_config["machine_type"],
                "disk_size_gb": 100,
                "disk_type": "pd-standard",
                "oauth_scopes": [
                    "https://www.googleapis.com/auth/cloud-platform"
                ]
            },
            "autoscaling": {
                "min_node_count": env_config["min_nodes"],
                "max_node_count": env_config["max_nodes"]
            }
        }
    }
    
    config.update(overrides)
    return config


def get_gcp_region_choices() -> List[Dict[str, str]]:
    """
    Get list of common GCP regions
    
    Returns:
        List of dicts with value and label for each region
    """
    return [
        {"value": "us-east1", "label": "US East (South Carolina)"},
        {"value": "us-east4", "label": "US East (Northern Virginia)"},
        {"value": "us-west1", "label": "US West (Oregon)"},
        {"value": "us-west2", "label": "US West (Los Angeles)"},
        {"value": "us-west3", "label": "US West (Salt Lake City)"},
        {"value": "us-west4", "label": "US West (Las Vegas)"},
        {"value": "us-central1", "label": "US Central (Iowa)"},
        {"value": "us-south1", "label": "US South (Dallas)"},
        {"value": "northamerica-northeast1", "label": "Canada (Montreal)"},
        {"value": "northamerica-northeast2", "label": "Canada (Toronto)"},
        {"value": "southamerica-east1", "label": "Brazil (São Paulo)"},
        {"value": "southamerica-west1", "label": "Chile (Santiago)"},
        {"value": "europe-west1", "label": "Europe (Belgium)"},
        {"value": "europe-west2", "label": "Europe (London)"},
        {"value": "europe-west3", "label": "Europe (Frankfurt)"},
        {"value": "europe-west4", "label": "Europe (Netherlands)"},
        {"value": "europe-west6", "label": "Europe (Zurich)"},
        {"value": "europe-north1", "label": "Europe (Finland)"},
        {"value": "europe-central2", "label": "Europe (Warsaw)"},
        {"value": "asia-east1", "label": "Asia (Taiwan)"},
        {"value": "asia-east2", "label": "Asia (Hong Kong)"},
        {"value": "asia-northeast1", "label": "Asia (Tokyo)"},
        {"value": "asia-northeast2", "label": "Asia (Osaka)"},
        {"value": "asia-northeast3", "label": "Asia (Seoul)"},
        {"value": "asia-south1", "label": "Asia (Mumbai)"},
        {"value": "asia-south2", "label": "Asia (Delhi)"},
        {"value": "asia-southeast1", "label": "Asia (Singapore)"},
        {"value": "asia-southeast2", "label": "Asia (Jakarta)"},
        {"value": "australia-southeast1", "label": "Australia (Sydney)"},
        {"value": "australia-southeast2", "label": "Australia (Melbourne)"},
        {"value": "me-west1", "label": "Middle East (Tel Aviv)"},
        {"value": "africa-south1", "label": "Africa (Johannesburg)"}
    ]
