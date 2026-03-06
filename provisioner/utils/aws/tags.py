"""
AWS Helper Functions - Resource Tagging

Provides consistent tagging strategies for all AWS resources.
"""

from typing import Dict


def get_standard_tags(
    project: str,
    environment: str,
    template: str,
    **additional_tags
) -> Dict[str, str]:
    """
    Generate standard Archie tags for AWS resources
    
    Args:
        project: Project name
        environment: Environment (dev, test, staging, prod)
        template: Template name that created this resource
        **additional_tags: Any additional tags to merge
    
    Returns:
        dict: Standard tag dictionary
    
    Example:
        >>> tags = get_standard_tags(
        ...     project="myapp",
        ...     environment="prod",
        ...     template="vpc-production-3tier",
        ...     Owner="devops@company.com"
        ... )
        >>> tags
        {
            "Project": "myapp",
            "Environment": "prod",
            "ManagedBy": "Archie",
            "Template": "vpc-production-3tier",
            "Owner": "devops@company.com"
        }
    """
    tags = {
        "Project": project,
        "Environment": environment,
        "ManagedBy": "Archie",
        "Template": template
    }
    
    # Merge any additional tags
    tags.update(additional_tags)
    
    return tags


def get_resource_name_tag(project: str, environment: str, resource_type: str, suffix: str = "") -> str:
    """
    Generate consistent resource Name tag
    
    Args:
        project: Project name
        environment: Environment
        resource_type: Type of resource (vpc, subnet, igw, etc.)
        suffix: Optional suffix (e.g., AZ name, index)
    
    Returns:
        str: Name tag value
    
    Example:
        >>> get_resource_name_tag("myapp", "prod", "vpc")
        "myapp-prod-vpc"
        >>> get_resource_name_tag("myapp", "prod", "subnet", "us-east-1a")
        "myapp-prod-subnet-us-east-1a"
    """
    parts = [project, environment, resource_type]
    if suffix:
        parts.append(suffix)
    return "-".join(parts)


def get_vpc_tags(project: str, environment: str, template: str, **additional_tags) -> Dict[str, str]:
    """
    Get standard tags for VPC with Name tag
    
    Args:
        project: Project name
        environment: Environment
        template: Template name
        **additional_tags: Additional tags
    
    Returns:
        dict: VPC tags with Name
    """
    tags = get_standard_tags(project, environment, template, **additional_tags)
    tags["Name"] = get_resource_name_tag(project, environment, "vpc")
    return tags


def get_subnet_tags(
    project: str,
    environment: str,
    template: str,
    tier: str,
    az: str,
    **additional_tags
) -> Dict[str, str]:
    """
    Get standard tags for Subnet with tier and AZ information
    
    Args:
        project: Project name
        environment: Environment
        template: Template name
        tier: Subnet tier (public, private, database)
        az: Availability zone
        **additional_tags: Additional tags
    
    Returns:
        dict: Subnet tags with Name and Tier
    """
    tags = get_standard_tags(project, environment, template, **additional_tags)
    tags["Name"] = get_resource_name_tag(project, environment, tier, az)
    tags["Tier"] = tier
    
    # Add Kubernetes ELB tags for public/private subnets
    if tier == "public":
        tags["kubernetes.io/role/elb"] = "1"
    elif tier == "private":
        tags["kubernetes.io/role/internal-elb"] = "1"
    
    return tags


def get_igw_tags(project: str, environment: str, template: str, **additional_tags) -> Dict[str, str]:
    """
    Get standard tags for Internet Gateway
    
    Args:
        project: Project name
        environment: Environment
        template: Template name
        **additional_tags: Additional tags
    
    Returns:
        dict: IGW tags
    """
    tags = get_standard_tags(project, environment, template, **additional_tags)
    tags["Name"] = get_resource_name_tag(project, environment, "igw")
    return tags


def get_nat_gateway_tags(
    project: str,
    environment: str,
    template: str,
    az: str,
    **additional_tags
) -> Dict[str, str]:
    """
    Get standard tags for NAT Gateway
    
    Args:
        project: Project name
        environment: Environment
        template: Template name
        az: Availability zone
        **additional_tags: Additional tags
    
    Returns:
        dict: NAT Gateway tags
    """
    tags = get_standard_tags(project, environment, template, **additional_tags)
    tags["Name"] = get_resource_name_tag(project, environment, "nat", az)
    return tags


def get_route_table_tags(
    project: str,
    environment: str,
    template: str,
    tier: str,
    az: str = "",
    **additional_tags
) -> Dict[str, str]:
    """
    Get standard tags for Route Table
    
    Args:
        project: Project name
        environment: Environment
        template: Template name
        tier: Route table tier (public, private, database)
        az: Availability zone (optional, for private route tables)
        **additional_tags: Additional tags
    
    Returns:
        dict: Route table tags
    """
    tags = get_standard_tags(project, environment, template, **additional_tags)
    
    if az:
        tags["Name"] = get_resource_name_tag(project, environment, f"{tier}-rt", az)
    else:
        tags["Name"] = get_resource_name_tag(project, environment, f"{tier}-rt")
    
    return tags


def get_security_group_tags(
    project: str,
    environment: str,
    template: str,
    sg_name: str = "",
    **additional_tags
) -> Dict[str, str]:
    """
    Get standard tags for Security Group
    
    Args:
        project: Project name
        environment: Environment
        template: Template name
        sg_name: Security group name/purpose (optional)
        **additional_tags: Additional tags
    
    Returns:
        dict: Security group tags
    """
    tags = get_standard_tags(project, environment, template, **additional_tags)
    
    if sg_name:
        tags["Name"] = get_resource_name_tag(project, environment, "sg", sg_name)
    else:
        tags["Name"] = get_resource_name_tag(project, environment, "sg")
    
    return tags


def get_s3_bucket_tags(
    project: str,
    environment: str,
    template: str,
    purpose: str = "",
    **additional_tags
) -> Dict[str, str]:
    """
    Get standard tags for S3 Bucket
    
    Args:
        project: Project name
        environment: Environment
        template: Template name
        purpose: Bucket purpose (static-website, logs, assets, etc.)
        **additional_tags: Additional tags
    
    Returns:
        dict: S3 bucket tags
    """
    tags = get_standard_tags(project, environment, template, **additional_tags)
    
    if purpose:
        tags["Purpose"] = purpose
    
    return tags


def get_iam_role_tags(
    project: str,
    environment: str,
    template: str,
    service: str = "",
    **additional_tags
) -> Dict[str, str]:
    """
    Get standard tags for IAM Role
    
    Args:
        project: Project name
        environment: Environment
        template: Template name
        service: Service using this role (optional)
        **additional_tags: Additional tags
    
    Returns:
        dict: IAM role tags
    """
    tags = get_standard_tags(project, environment, template, **additional_tags)
    
    if service:
        tags["Service"] = service
    
    return tags
