"""
AWS Helper Functions - Defaults and Smart Generation

Provides smart defaults and auto-generation for AWS resources to avoid
configuration conflicts and follow best practices.
"""

import secrets
from typing import Dict, Any


def generate_vpc_cidr() -> str:
    """
    Generate a unique VPC CIDR block to avoid collisions
    
    Uses random second octet in 10.X.0.0/16 range.
    
    Returns:
        str: CIDR block like "10.142.0.0/16"
    """
    second_octet = secrets.randbelow(254) + 1  # 1-254
    return f"10.{second_octet}.0.0/16"


def generate_subnet_cidr(vpc_cidr: str, subnet_index: int = 1) -> str:
    """
    Generate subnet CIDR within a VPC CIDR block
    
    Args:
        vpc_cidr: VPC CIDR block (e.g., "10.0.0.0/16")
        subnet_index: Subnet index (1-254) for third octet
    
    Returns:
        str: Subnet CIDR like "10.0.1.0/24"
    
    Example:
        >>> vpc_cidr = "10.0.0.0/16"
        >>> generate_subnet_cidr(vpc_cidr, 1)
        "10.0.1.0/24"
    """
    base = vpc_cidr.split('/')[0]  # "10.0.0.0"
    octets = base.split('.')
    return f"{octets[0]}.{octets[1]}.{subnet_index}.0/24"


def derive_subnet_cidrs_from_vpc(vpc_cidr: str, count: int = 3) -> list[str]:
    """
    Derive multiple subnet CIDRs from VPC CIDR
    
    Args:
        vpc_cidr: VPC CIDR block
        count: Number of subnets to generate
    
    Returns:
        list: List of subnet CIDRs
    
    Example:
        >>> derive_subnet_cidrs_from_vpc("10.0.0.0/16", 3)
        ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
    """
    return [generate_subnet_cidr(vpc_cidr, i + 1) for i in range(count)]


def get_availability_zones(region: str, count: int = 3) -> list[str]:
    """
    Get availability zones for a region
    
    Args:
        region: AWS region (e.g., "us-east-1")
        count: Number of AZs to return
    
    Returns:
        list: List of AZ names
    
    Example:
        >>> get_availability_zones("us-east-1", 3)
        ["us-east-1a", "us-east-1b", "us-east-1c"]
    """
    az_suffixes = ['a', 'b', 'c', 'd', 'e', 'f']
    return [f"{region}{suffix}" for suffix in az_suffixes[:count]]


def get_smart_vpc_defaults(project_name: str, environment: str, region: str = "us-east-1") -> Dict[str, Any]:
    """
    Generate complete smart defaults for VPC non-prod template
    
    Args:
        project_name: Project name
        environment: Environment (dev, test, qa, staging)
        region: AWS region
    
    Returns:
        dict: Complete configuration with smart defaults
    """
    vpc_cidr = generate_vpc_cidr()
    
    return {
        "project_name": project_name,
        "environment": environment,
        "region": region,
        "vpc_cidr": vpc_cidr,
        "public_subnet_cidr": generate_subnet_cidr(vpc_cidr, 1),
        "availability_zone": f"{region}a",
        "enable_flow_logs": False
    }


def get_smart_vpc_prod_defaults(project_name: str, region: str = "us-east-1") -> Dict[str, Any]:
    """
    Generate complete smart defaults for VPC production template
    
    Args:
        project_name: Project name
        region: AWS region
    
    Returns:
        dict: Complete configuration with smart defaults for 3-tier VPC
    """
    vpc_cidr = generate_vpc_cidr()
    azs = get_availability_zones(region, 3)
    
    # Derive subnet CIDRs from VPC CIDR to ensure they're within range
    base = vpc_cidr.split('/')[0]
    octets = base.split('.')
    vpc_second_octet = octets[1]
    
    return {
        "project_name": project_name,
        "environment": "prod",
        "region": region,
        "vpc_cidr": vpc_cidr,
        "azs": azs,
        "public_subnet_cidrs": [
            f"10.{vpc_second_octet}.1.0/24",
            f"10.{vpc_second_octet}.2.0/24",
            f"10.{vpc_second_octet}.3.0/24"
        ],
        "private_subnet_cidrs": [
            f"10.{vpc_second_octet}.11.0/24",
            f"10.{vpc_second_octet}.12.0/24",
            f"10.{vpc_second_octet}.13.0/24"
        ],
        "database_subnet_cidrs": [
            f"10.{vpc_second_octet}.21.0/24",
            f"10.{vpc_second_octet}.22.0/24",
            f"10.{vpc_second_octet}.23.0/24"
        ],
        "enable_nat_gateway": True,
        "single_nat_gateway": False,  # HA by default
        "enable_flow_logs": True,
        "enable_vpc_endpoints": True,
        "flow_logs_retention_days": 30
    }
