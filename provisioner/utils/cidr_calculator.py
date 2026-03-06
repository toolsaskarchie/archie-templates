"""
Utility functions for calculating subnet CIDRs from VPC CIDR blocks.
"""
import ipaddress
from typing import List, Tuple


def calculate_subnet_cidrs(vpc_cidr: str, num_azs: int = 2) -> Tuple[List[str], List[str]]:
    """
    Calculate subnet CIDRs for public and private subnets from a VPC CIDR using proper CIDR math.
    
    Uses Python's ipaddress library to properly subdivide the VPC CIDR into subnets,
    ensuring no overlaps and valid CIDR blocks.
    
    Args:
        vpc_cidr: VPC CIDR block (e.g., "10.0.0.0/16")
        num_azs: Number of availability zones (default: 2)
    
    Returns:
        Tuple of (public_subnet_cidrs, private_subnet_cidrs)
        
    Example:
        For VPC CIDR "10.0.0.0/16":
        - Public subnets: ["10.0.0.0/24", "10.0.1.0/24"]
        - Private subnets: ["10.0.2.0/24", "10.0.3.0/24"]
        
        For VPC CIDR "172.31.0.0/16":
        - Public subnets: ["172.31.0.0/24", "172.31.1.0/24"]
        - Private subnets: ["172.31.2.0/24", "172.31.3.0/24"]
        
        For VPC CIDR "10.227.0.0/16":
        - Public subnets: ["10.227.0.0/24", "10.227.1.0/24"]
        - Private subnets: ["10.227.2.0/24", "10.227.3.0/24"]
    """
    network = ipaddress.IPv4Network(vpc_cidr, strict=False)
    
    # Determine subnet prefix based on VPC CIDR
    # For /16 VPC -> /24 subnets (256 subnets available)
    # For /20 VPC -> /24 subnets (16 subnets available)
    # For /24 VPC -> /26 subnets (4 subnets available)
    vpc_prefix = network.prefixlen
    
    if vpc_prefix <= 16:
        subnet_prefix = 24  # /24 gives 256 hosts per subnet
    elif vpc_prefix <= 20:
        subnet_prefix = 24  # /24 still works for /20 VPC
    elif vpc_prefix <= 24:
        subnet_prefix = 26  # /26 gives 64 hosts per subnet
    else:
        subnet_prefix = 28  # /28 gives 16 hosts per subnet (for very small VPCs)
    
    # Generate all possible subnets with the target prefix
    try:
        subnets = list(network.subnets(new_prefix=subnet_prefix))
    except ValueError:
        # If subdivision fails, use the original network (single subnet scenario)
        subnets = [network]
    
    # Ensure we have enough subnets for public + private across all AZs
    required_subnets = num_azs * 2
    if len(subnets) < required_subnets:
        raise ValueError(
            f"VPC CIDR {vpc_cidr} cannot be subdivided into {required_subnets} /{subnet_prefix} subnets. "
            f"Only {len(subnets)} subnets available. Consider using a larger VPC CIDR block."
        )
    
    # Allocate subnets:
    # - First num_azs subnets for public
    # - Next num_azs subnets for private
    public_cidrs = [str(subnets[i]) for i in range(num_azs)]
    private_cidrs = [str(subnets[i + num_azs]) for i in range(num_azs)]
    
    return public_cidrs, private_cidrs


def get_subnet_cidr(vpc_cidr: str, subnet_type: str, az_index: int, num_azs: int = 2) -> str:
    """
    Get a single subnet CIDR from VPC CIDR using proper CIDR subdivision.
    
    Args:
        vpc_cidr: VPC CIDR block (e.g., "10.0.0.0/16")
        subnet_type: "public" or "private"
        az_index: Availability zone index (0, 1, 2, etc.)
        num_azs: Total number of availability zones (default: 2)
    
    Returns:
        Subnet CIDR (e.g., "10.0.0.0/24")
    """
    public_cidrs, private_cidrs = calculate_subnet_cidrs(vpc_cidr, num_azs)
    
    if subnet_type == "public":
        if az_index >= len(public_cidrs):
            raise ValueError(f"az_index {az_index} out of range for {len(public_cidrs)} public subnets")
        return public_cidrs[az_index]
    elif subnet_type == "private":
        if az_index >= len(private_cidrs):
            raise ValueError(f"az_index {az_index} out of range for {len(private_cidrs)} private subnets")
        return private_cidrs[az_index]
    else:
        raise ValueError(f"Invalid subnet_type: {subnet_type}. Must be 'public' or 'private'")
