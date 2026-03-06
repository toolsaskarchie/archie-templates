"""
GCP Utilities Package

Provides helper functions for GCP resource management:
- defaults: Smart defaults and auto-configuration
- labels: Standard labeling strategies (GCP uses "labels" not "tags")
- naming: Resource naming conventions
"""

from .defaults import (
    get_smart_bucket_config,
    get_smart_instance_config,
    get_smart_vpc_config,
    get_smart_subnet_config,
    get_smart_cloud_sql_config,
    get_smart_cloud_run_config,
    get_smart_gke_cluster_config,
    get_gcp_region_choices,
)

from .labels import (
    get_standard_labels,
    get_bucket_labels,
    get_instance_labels,
    get_vpc_labels,
    get_subnet_labels,
    get_cloud_sql_labels,
    get_cloud_run_labels,
    get_gke_cluster_labels,
    get_cloud_function_labels,
    get_pubsub_topic_labels,
    get_load_balancer_labels,
    get_cloud_armor_labels,
    get_cloud_cdn_labels,
)

from .naming import (
    get_resource_name,
    get_bucket_name,
    get_instance_name,
    get_vpc_name,
    get_subnet_name,
    get_firewall_rule_name,
    get_cloud_sql_instance_name,
    get_cloud_run_service_name,
    get_gke_cluster_name,
    get_cloud_function_name,
    get_pubsub_topic_name,
    get_secret_name,
    get_load_balancer_name,
    get_service_account_name,
    get_cloud_armor_policy_name,
    get_cloud_cdn_name,
)

__all__ = [
    # defaults
    "get_smart_bucket_config",
    "get_smart_instance_config",
    "get_smart_vpc_config",
    "get_smart_subnet_config",
    "get_smart_cloud_sql_config",
    "get_smart_cloud_run_config",
    "get_smart_gke_cluster_config",
    "get_gcp_region_choices",
    # labels
    "get_standard_labels",
    "get_bucket_labels",
    "get_instance_labels",
    "get_vpc_labels",
    "get_subnet_labels",
    "get_cloud_sql_labels",
    "get_cloud_run_labels",
    "get_gke_cluster_labels",
    "get_cloud_function_labels",
    "get_pubsub_topic_labels",
    "get_load_balancer_labels",
    "get_cloud_armor_labels",
    "get_cloud_cdn_labels",
    # naming
    "get_resource_name",
    "get_bucket_name",
    "get_instance_name",
    "get_vpc_name",
    "get_subnet_name",
    "get_firewall_rule_name",
    "get_cloud_sql_instance_name",
    "get_cloud_run_service_name",
    "get_gke_cluster_name",
    "get_cloud_function_name",
    "get_pubsub_topic_name",
    "get_secret_name",
    "get_load_balancer_name",
    "get_service_account_name",
    "get_cloud_armor_policy_name",
    "get_cloud_cdn_name",
]
