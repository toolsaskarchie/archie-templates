"""Base configuration class for all templates."""
from typing import Dict, Any, Optional


class TemplateConfig:
    """Base configuration class that all template configs should extend.
    
    Provides common utilities for accessing nested config data and
    handling provider-specific parameters.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize with raw config dictionary.
        
        Args:
            config: The full configuration dictionary from deployment request
        """
        self.raw = config
        self.parameters = config.get('parameters', {})
    
    def get_provider_config(self, provider: str) -> Dict[str, Any]:
        """Get provider-specific configuration block.
        
        Args:
            provider: Provider name (aws, gcp, azure)
            
        Returns:
            Provider config dictionary, empty dict if not found
        """
        return self.parameters.get(provider, {})
    
    def get_parameter(self, key: str, default: Any = None) -> Any:
        """Get a top-level parameter value with default.
        
        Args:
            key: Parameter key
            default: Default value if key not found
            
        Returns:
            Parameter value or default
        """
        return self.parameters.get(key, default)
    
    def get_nested_parameter(self, *keys: str, default: Any = None) -> Any:
        """Get a nested parameter value using a path of keys.
        
        Args:
            *keys: Sequence of keys to navigate (e.g., 'aws', 'region')
            default: Default value if path not found
            
        Returns:
            Nested value or default
        """
        current = self.parameters
        for key in keys:
            if isinstance(current, dict):
                current = current.get(key)
                if current is None:
                    return default
            else:
                return default
        return current if current is not None else default
