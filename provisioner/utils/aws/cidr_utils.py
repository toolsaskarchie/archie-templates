"""
Utility functions for CIDR block generation and management
"""

import random
import ipaddress
from typing import List


def generate_random_vpc_cidr(prefix_length: int = 16) -> str:
    """
    Generate a random VPC CIDR block from 10.0.0.0/8 range
    
    Uses only the 10.0.0.0/8 private address space for consistency
    and to avoid conflicts with corporate networks.
    
    Args:
        prefix_length: CIDR prefix length (default: 16 for /16 networks)
        
    Returns:
        Random CIDR block string (e.g., "10.123.0.0/16")
    """
    # Use only 10.0.0.0/8 range
    base_network = ipaddress.ip_network("10.0.0.0/8")
    
    # Generate subnets of desired size
    subnets = list(base_network.subnets(new_prefix=prefix_length))
    
    # Choose a random subnet
    random_subnet = random.choice(subnets)
    
    return str(random_subnet)


def is_valid_cidr(cidr: str) -> bool:
    """
    Validate if a string is a valid CIDR block
    
    Args:
        cidr: CIDR block string to validate
        
    Returns:
        True if valid, False otherwise
    """
    try:
        ipaddress.ip_network(cidr)
        return True
    except (ValueError, ipaddress.AddressValueError, ipaddress.NetmaskValueError):
        return False


def is_private_cidr(cidr: str) -> bool:
    """
    Check if a CIDR block is in private IP space
    
    Args:
        cidr: CIDR block string
        
    Returns:
        True if private, False otherwise
    """
    try:
        network = ipaddress.ip_network(cidr)
        return network.is_private
    except (ValueError, ipaddress.AddressValueError, ipaddress.NetmaskValueError):
        return False


def calculate_subnet_cidrs(vpc_cidr: str, count: int, subnet_prefix: int = 20) -> List[str]:
    """
    Calculate subnet CIDR blocks from a VPC CIDR
    
    Args:
        vpc_cidr: VPC CIDR block (e.g., "10.0.0.0/16")
        count: Number of subnets to create
        subnet_prefix: Prefix length for subnets (default: 20)
        
    Returns:
        List of subnet CIDR blocks
    """
    network = ipaddress.ip_network(vpc_cidr)
    subnets = list(network.subnets(new_prefix=subnet_prefix))
    
    if count > len(subnets):
        raise ValueError(
            f"Cannot create {count} /{subnet_prefix} subnets from {vpc_cidr}. "
            f"Maximum possible: {len(subnets)}"
        )
    
    return [str(subnet) for subnet in subnets[:count]]
