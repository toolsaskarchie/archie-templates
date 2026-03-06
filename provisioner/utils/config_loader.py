"""
Configuration Loader Utility

Loads template configurations from YAML files (defaults.yaml).
This centralizes all resource configurations in one place for easy modification.
"""

from pathlib import Path
from typing import Any, Dict, Optional
import yaml


class TemplateConfigLoader:
    """Loads and manages template configuration from YAML files."""
    
    def __init__(self, template_dir: Path):
        """
        Initialize config loader for a template directory.
        
        Args:
            template_dir: Path to the template directory containing defaults.yaml
        """
        self.template_dir = Path(template_dir)
        self.config_file = self.template_dir / "defaults.yaml"
        self._config: Optional[Dict[str, Any]] = None
    
    @property
    def config(self) -> Dict[str, Any]:
        """Load and cache configuration from YAML file."""
        if self._config is None:
            self._config = self._load_config()
        return self._config
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from defaults.yaml file."""
        if not self.config_file.exists():
            print(f"⚠️  Warning: {self.config_file} not found, using empty config")
            return {}
        
        try:
            with open(self.config_file, 'r') as f:
                config = yaml.safe_load(f) or {}
                print(f"✅ Loaded configuration from {self.config_file}")
                return config
        except Exception as e:
            print(f"❌ Error loading {self.config_file}: {e}")
            return {}
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get a configuration value using dot notation.
        
        Args:
            key_path: Dot-separated path to the config value (e.g., "vpc.cidr_block")
            default: Default value if key not found
            
        Returns:
            Configuration value or default
            
        Example:
            loader.get("vpc.cidr_block")  # Returns "10.0.0.0/16"
            loader.get("security_groups.web.ingress")  # Returns list of ingress rules
        """
        keys = key_path.split('.')
        value = self.config
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        
        return value
    
    def get_vpc_config(self) -> Dict[str, Any]:
        """Get VPC configuration section."""
        return self.get("vpc", {})
    
    def get_subnets_config(self) -> Dict[str, Any]:
        """Get subnets configuration section."""
        return self.get("subnets", {})
    
    def get_security_groups_config(self) -> Dict[str, Any]:
        """Get security groups configuration section."""
        return self.get("security_groups", {})
    
    def get_nat_gateway_config(self) -> Dict[str, Any]:
        """Get NAT gateway configuration section."""
        return self.get("nat_gateway", {})
    
    def get_flow_logs_config(self) -> Dict[str, Any]:
        """Get flow logs configuration section."""
        return self.get("flow_logs", {})
    
    def get_vpc_endpoints_config(self) -> Dict[str, Any]:
        """Get VPC endpoints configuration section."""
        return self.get("vpc_endpoints", {})
    
    def get_network_acl_config(self) -> Dict[str, Any]:
        """Get network ACL configuration section."""
        return self.get("network_acl", {})
    
    def get_tags_config(self) -> Dict[str, Any]:
        """Get tags configuration section."""
        return self.get("tags", {})
    
    @staticmethod
    def load_from_template_dir(template_dir: Path) -> Dict[str, Any]:
        """
        Static method to quickly load config from a template directory.
        
        Args:
            template_dir: Path to template directory
            
        Returns:
            Configuration dictionary
        """
        loader = TemplateConfigLoader(template_dir)
        return loader.config
