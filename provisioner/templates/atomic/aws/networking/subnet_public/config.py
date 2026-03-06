"""
Configuration class for Public Subnet template
"""

from typing import Dict, Any, Optional

class PublicSubnetConfig:
    """
    Configuration wrapper for Public Subnet template
    Handles parameter extraction and defaults
    """
    def __init__(self, config: Dict[str, Any]):
        self.config = config
    def get_parameter(self, key: str, default: Any = None) -> Any:
        return self.config.get(key, default)
    @property
    def vpc_mode(self) -> str:
        mode = self.get_parameter('vpcMode') or self.get_parameter('vpc_mode', 'new')
        if mode not in ['new', 'existing']:
            raise ValueError(f"Invalid vpc_mode: {mode}. Must be 'new' or 'existing'")
        return mode
    @property
    def vpc_id(self) -> Optional[str]:
        vpc_id = self.get_parameter('vpcId') or self.get_parameter('vpc_id')
        if self.vpc_mode == 'existing' and not vpc_id:
            raise ValueError("VPC ID is required when using existing VPC mode")
        return vpc_id
    @property
    def vpc_name(self) -> str:
        return self.get_parameter('vpcName') or self.get_parameter('vpc_name', 'archie-vpc')
    @property
    def vpc_cidr(self) -> str:
        return self.get_parameter('vpcCidr') or self.get_parameter('vpc_cidr', '10.0.0.0/16')
    @property
    def subnet_name(self) -> str:
        return self.get_parameter('subnetName') or self.get_parameter('subnet_name', 'public-subnet')
    @property
    def cidr_block(self) -> str:
        cidr = self.get_parameter('cidrBlock') or self.get_parameter('cidr_block', '10.0.1.0/24')
        return cidr
