"""
AWS Helper Utilities

This package provides helper functions for AWS resource provisioning:
- defaults: Smart defaults and auto-generation (CIDR, subnets, configs)
- tags: Standard tagging strategies
- naming: Consistent resource naming conventions
"""

from .defaults import (
    generate_vpc_cidr,
    generate_subnet_cidr,
    derive_subnet_cidrs_from_vpc,
    get_availability_zones,
    get_smart_vpc_defaults,
    get_smart_vpc_prod_defaults
)

from .tags import (
    get_standard_tags,
    get_resource_name_tag,
    get_vpc_tags,
    get_subnet_tags,
    get_igw_tags,
    get_nat_gateway_tags,
    get_route_table_tags,
    get_security_group_tags,
    get_s3_bucket_tags,
    get_iam_role_tags
)

from .naming import (
    get_resource_name,
    get_vpc_name,
    get_subnet_name,
    get_igw_name,
    get_nat_gateway_name,
    get_eip_name,
    get_route_table_name,
    get_security_group_name,
    get_s3_bucket_name,
    get_iam_role_name,
    get_lambda_function_name,
    get_cloudwatch_log_group_name,
    get_rds_identifier,
    get_alb_name,
    get_ecs_cluster_name,
    get_eks_cluster_name,
    get_region_shortcode,
    sanitize_name,
    ResourceNamer  # NEW: Self-documenting resource namer
)

__all__ = [
    # Defaults
    "generate_vpc_cidr",
    "generate_subnet_cidr",
    "derive_subnet_cidrs_from_vpc",
    "get_availability_zones",
    "get_smart_vpc_defaults",
    "get_smart_vpc_prod_defaults",
    
    # Tags
    "get_standard_tags",
    "get_resource_name_tag",
    "get_vpc_tags",
    "get_subnet_tags",
    "get_igw_tags",
    "get_nat_gateway_tags",
    "get_route_table_tags",
    "get_security_group_tags",
    "get_s3_bucket_tags",
    "get_iam_role_tags",
    
    # Naming
    "get_resource_name",
    "get_vpc_name",
    "get_subnet_name",
    "get_igw_name",
    "get_nat_gateway_name",
    "get_eip_name",
    "get_route_table_name",
    "get_security_group_name",
    "get_s3_bucket_name",
    "get_iam_role_name",
    "get_lambda_function_name",
    "get_cloudwatch_log_group_name",
    "get_rds_identifier",
    "get_alb_name",
    "get_ecs_cluster_name",
    "get_eks_cluster_name",
    "sanitize_name",
    "get_region_shortcode",
    "ResourceNamer",  # NEW: Self-documenting resource namer class
]
