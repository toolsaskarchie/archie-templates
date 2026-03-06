"""Configuration for Azure VNet Atomic template"""
from dataclasses import dataclass
from typing import Any, Dict, List

@dataclass
class VNetAtomicConfig:
    """Configuration for atomic Azure VNet"""
    vnet_name: str
    resource_group_name: str
    location: str
    address_prefixes: List[str]
    project_name: str
    environment: str
    
    def __init__(self, config: Dict[str, Any]):
        # Support both direct config and nested parameters structure
        params = config.get('parameters', config)
        
        # Extract core configuration
        self.vnet_name = (
            params.get('vnetName') or 
            params.get('vnet_name') or 
            params.get('projectName', 'my-vnet')
        )
        
        self.resource_group_name = (
            params.get('resourceGroupName') or
            params.get('resource_group_name') or
            f"{self.vnet_name}-rg"
        )
        
        self.location = params.get('location', 'eastus')
        
        # Parse address prefixes
        address_prefixes = params.get('addressPrefixes') or params.get('address_prefixes')
        if isinstance(address_prefixes, str):
            # Single CIDR block as string
            self.address_prefixes = [address_prefixes]
        elif isinstance(address_prefixes, list):
            self.address_prefixes = address_prefixes
        else:
            # Default
            self.address_prefixes = ['10.0.0.0/16']
        
        self.project_name = params.get('projectName', 'my-project')
        self.environment = params.get('environment', 'dev')
        
        # Validate
        self._validate()
    
    def _validate(self):
        """Validate required configuration"""
        if not self.vnet_name:
            raise ValueError("vnetName is required")
        
        if not self.location:
            raise ValueError("location is required")
        
        if not self.address_prefixes or len(self.address_prefixes) == 0:
            raise ValueError("addressPrefixes must contain at least one CIDR block")
        
        # Validate CIDR format (basic check)
        for cidr in self.address_prefixes:
            if '/' not in cidr:
                raise ValueError(f"Invalid CIDR format: {cidr}")
