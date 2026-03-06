"""
Template Configuration Loader

Loads and merges configuration from template.yaml with user input.
Replaces the old config.py + defaults.yaml approach.
"""

import yaml
from pathlib import Path
from typing import Any, Dict, Optional


class TemplateConfig:
    """
    Loads template.yaml and merges with user input.
    
    Priority: user_input > template.yaml defaults
    """
    
    def __init__(self, template_dir: Path, user_input: Optional[Dict[str, Any]] = None):
        """
        Initialize template configuration.
        
        Args:
            template_dir: Path to template directory containing template.yaml
            user_input: User configuration (overrides defaults)
        """
        self.template_dir = Path(template_dir)
        self.template_yaml_path = self.template_dir / "template.yaml"
        
        # Load template.yaml
        with open(self.template_yaml_path, 'r') as f:
            self.template_spec = yaml.safe_load(f)
        
        # Extract configuration schema
        config_root = self.template_spec.get('configuration', {})
        self.config_schema = config_root.get('properties', config_root)
        
        # Extract user input from parameters
        self.user_input = {}
        if user_input:
            # Support both direct parameters and nested structure
            if 'parameters' in user_input:
                params = user_input['parameters']
                # Could be nested as parameters.aws or just parameters
                if 'aws' in params:
                    self.user_input = params['aws']
                else:
                    self.user_input = params
            else:
                self.user_input = user_input
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value with priority: user_input > template defaults > default arg.
        
        Args:
            key: Configuration key
            default: Fallback default if not found
            
        Returns:
            Configuration value
        """
        # Check user input first
        if key in self.user_input:
            return self.user_input[key]
        
        # Check template.yaml defaults
        if key in self.config_schema:
            schema_item = self.config_schema[key]
            if isinstance(schema_item, dict) and 'default' in schema_item:
                return schema_item['default']
        
        # Fallback to provided default
        return default
    
    def __getattr__(self, name: str) -> Any:
        """
        Allow accessing configuration values as attributes.
        
        Example: config.vpc_mode instead of config.get('vpc_mode')
        """
        # If the attribute starts with _, don't try to resolve it from config
        if name.startswith('_'):
            raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")
            
        val = self.get(name)
        if val is None:
            # Check if it exists in schema to distinguish between mismatch and deliberate None
            if name not in self.config_schema and name not in self.user_input:
                # Special cases for common Archie props that might not be in schema
                if name in ['project_name', 'region', 'environment', 'cidr_block']:
                    return self.get(name)
                raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")
        return val
    
    def get_all(self) -> Dict[str, Any]:
        """
        Get all configuration values (merged defaults + user input).
        
        Returns:
            Complete configuration dictionary
        """
        config = {}
        
        # Start with all defaults from template.yaml
        for key, schema_item in self.config_schema.items():
            if isinstance(schema_item, dict) and 'default' in schema_item:
                config[key] = schema_item['default']
        
        # Override with user input
        config.update(self.user_input)
        
        return config
    
    def should_create_resource(self, resource_name: str) -> bool:
        """
        Check if a resource should be created based on conditions.
        
        Args:
            resource_name: Resource identifier from template.yaml
            
        Returns:
            True if resource should be created
        """
        resources = self.template_spec.get('resources', {})
        
        if resource_name not in resources:
            return False
        
        resource = resources[resource_name]
        
        # Always create if marked as such
        if resource.get('always_created', False):
            return True
        
        # Check conditional
        if 'conditional' in resource:
            condition = resource['conditional']
            return self._evaluate_condition(condition)
        
        # Default to creating if no condition specified
        return True
    
    def _evaluate_condition(self, condition: str) -> bool:
        """
        Evaluate a simple condition string.
        
        Args:
            condition: Condition string (e.g., "enable_high_availability == true")
            
        Returns:
            True if condition is met
        """
        # Simple evaluation for common patterns
        # Format: "config_key == value"
        if '==' in condition:
            parts = condition.split('==')
            if len(parts) == 2:
                key = parts[0].strip()
                expected_value = parts[1].strip()
                
                # Get actual value
                actual_value = self.get(key)
                
                # Compare
                if expected_value.lower() == 'true':
                    return actual_value is True
                elif expected_value.lower() == 'false':
                    return actual_value is False
                else:
                    return str(actual_value) == expected_value
        
        # Default to False if can't evaluate
        return False
    
    def get_metadata(self) -> Dict[str, Any]:
        """Get template metadata."""
        return self.template_spec.get('metadata', {})
    
    def get_resources_spec(self) -> Dict[str, Any]:
        """Get resources specification."""
        return self.template_spec.get('resources', {})
    
    def calculate_cost(self) -> float:
        """
        Calculate estimated monthly cost based on configuration.
        
        Returns:
            Estimated cost in USD/month
        """
        cost_calc = self.template_spec.get('cost_calculator', {})
        base_cost = cost_calc.get('base_cost', 0)
        components = cost_calc.get('components', {})
        
        total_cost = base_cost
        
        for component_name, component_spec in components.items():
            # Check if component should be included
            if component_spec.get('always_included', False):
                total_cost += component_spec.get('cost', 0)
            elif 'condition' in component_spec:
                if self._evaluate_condition(component_spec['condition']):
                    total_cost += component_spec.get('cost', 0)
        
        return total_cost
    
    # Convenience properties for common config values
    
    @property
    def project_name(self) -> str:
        return self.get('project_name') or self.get('projectName') or 'vpc-nonprod'
    
    @property
    def region(self) -> str:
        return self.get('region', 'us-east-1')
    
    @property
    def environment(self) -> str:
        return self.get('environment', 'prod')

    @property
    def cidr_block(self) -> str:
        return self.get('cidr_block', '10.0.0.0/16')
    
    @property
    def enable_dns_support(self) -> bool:
        return self.get('enable_dns_support', True)
    
    @property
    def enable_dns_hostnames(self) -> bool:
        return self.get('enable_dns_hostnames', True)
    
    @property
    def instance_tenancy(self) -> str:
        return self.get('instance_tenancy', 'default')
    
    @property
    def az_1(self) -> str:
        az = self.get('az_1', '')
        return az if az else f'{self.region}a'
    
    @property
    def az_2(self) -> str:
        az = self.get('az_2', '')
        return az if az else f'{self.region}b'
    
    @property
    def enable_high_availability(self) -> bool:
        return self.get('enable_high_availability', False)
    
    @property
    def enable_isolated_tier(self) -> bool:
        return self.get('enable_isolated_tier', False)
    
    @property
    def enable_rds_endpoint(self) -> bool:
        return self.get('enable_rds_endpoint', False)
    
    @property
    def enable_ssm_endpoints(self) -> bool:
        return self.get('enable_ssm_endpoints', False)
    
    @property
    def enable_flow_logs(self) -> bool:
        return self.get('enable_flow_logs', True)
    
    @property
    def flow_log_retention(self) -> int:
        return int(self.get('flow_log_retention', 7))
    
    @property
    def enable_s3_endpoint(self) -> bool:
        return self.get('enable_s3_endpoint', True)
    
    @property
    def enable_dynamodb_endpoint(self) -> bool:
        return self.get('enable_dynamodb_endpoint', True)
    
    @property
    def tags(self) -> Dict[str, str]:
        return self.get('tags', {})
