"""
Base Template Classes

Base classes and registry for infrastructure templates.
Templates combine multiple modules to create complete deployable infrastructure.
"""

from typing import Any, Dict, List, Optional, Type
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
import pulumi


class TemplateCategory(str, Enum):
    """Template categories"""
    NETWORKING = "networking"
    COMPUTE = "compute" 
    DATABASE = "database"
    SERVERLESS = "serverless"
    CONTAINERS = "containers"
    STORAGE = "storage"
    WEBSITE = "website"
    MONITORING = "monitoring"
    SECURITY = "security"
    FULL_STACK = "full_stack"
    KUBERNETES = "kubernetes"
    Kubernetes = "kubernetes" # Backward compatibility
    CUSTOM = "custom"


@dataclass
class TemplateMetadata:
    """Metadata for infrastructure templates"""
    name: str
    description: str
    category: TemplateCategory
    version: str
    author: str
    tags: List[str]
    estimated_cost: str
    complexity: str
    deployment_time: str
    modules: List[str] = None
    prerequisites: List[str] = None
    supported_regions: List[str] = None
    free_trial: bool = False
    marketplace_group: str = "NONE"
    title: str = None
    subtitle: str = ""
    features: List[str] = None
    use_cases: List[str] = None
    suggested_next_steps: List[str] = None # List of action_names for recommended follow-up templates
    
    # New fields for Unified Manifest
    requires_cloud_account: bool = True
    is_essential: bool = False
    is_listed_in_marketplace: bool = True
    cloud: str = "aws" # aws, gcp, azure
    pricing_model: str = "basic" # basic, elastic, reserve
    deployment_scope: str = "single-region" # single-region, multi-region, global
    certifications: List[str] = None # ["aws-well-architected"]
    pillars_text: List[str] = None
    pillars: Dict[str, Dict[str, Any]] = None # Well-architected pillar scores/details

    def __post_init__(self):
        """Handle camelCase to snake_case mapping for legacy templates"""
        pass
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        """Create metadata from dictionary, handling both snake_case and camelCase"""
        # Map camelCase to snake_case
        mapping = {
            'isListedInMarketplace': 'is_listed_in_marketplace',
            'requiresCloudAccount': 'requires_cloud_account',
            'isEssential': 'is_essential',
            'pricingModel': 'pricing_model',
            'deploymentScope': 'deployment_scope',
            'pillarsText': 'pillars_text'
        }
        
        clean_data = data.copy()
        for camel, snake in mapping.items():
            if camel in clean_data and snake not in clean_data:
                clean_data[snake] = clean_data.pop(camel)
        
        # Only keep keys that are in the dataclass fields
        import inspect
        valid_keys = inspect.signature(cls).parameters.keys()
        final_data = {k: v for k, v in clean_data.items() if k in valid_keys}
        
        return cls(**final_data)


class InfrastructureTemplate(ABC):
    """
    Base class for all infrastructure templates
    
    Templates represent complete, deployable infrastructure
    configurations that combine multiple modules.
    """
    
    def __init__(self, name: str, config: Dict[str, Any], **kwargs):
        self.name = name
        self.config = config
        self.modules = {}
        self.outputs = {}

    def get_parameter(self, key: str, default: Any = None) -> Any:
        """
        Get a template parameter, handling dynamic linking (StackReference) and smart defaults.
        """
        # 1. Check if this parameter or its parent resource is explicitly linked
        # Resolve using [key]_mode or [resource]_mode (e.g. vpc_id -> vpc)
        search_keys = [key]
        if '_' in key:
            search_keys.append(key.split('_')[0]) # Try 'vpc' if key is 'vpc_id'
            
        for lookup in search_keys:
            mode = self.config.get(f"{lookup}_mode")
            if mode == 'link-stack':
                source_stack = self.config.get(f"{lookup}_linked_stack_id")
                output_key = self.config.get(f"{lookup}_linked_output_key")
                
                if source_stack and output_key:
                    # Use Pulumi StackReference to fetch the value
                    try:
                        ref = pulumi.StackReference(source_stack)
                        return ref.get_output(output_key)
                    except Exception as e:
                        print(f"  ⚠ StackReference resolution failed for {source_stack}:{output_key} - {e}")
        
        # 2. Fallback to standard parameter from the 'parameters' object
        # Handle the common nested structure [parameters][aws/gcp/azure][key]
        parameters = self.config.get('parameters', {})
        if isinstance(parameters, dict):
            # Check for cloud-specific sub-parameter blocks
            for provider in ['aws', 'gcp', 'azure']:
                provider_params = parameters.get(provider, {})
                if isinstance(provider_params, dict) and key in provider_params:
                    return provider_params[key]
            
            if key in parameters:
                return parameters[key]
        
        # 3. Final fallback to top-level config or default
        return self.config.get(key, default)

    def get_bool(self, key: str, default: bool = False) -> bool:
        """Get a parameter as bool. Handles: True, 1, '1', 'true', Decimal(1)."""
        val = self.get_parameter(key, default)
        if isinstance(val, bool):
            return val
        if isinstance(val, (int, float)):
            return val != 0
        if isinstance(val, str):
            return val.lower() in ('true', '1', 'yes')
        # Handle Decimal
        try:
            return int(val) != 0
        except (TypeError, ValueError):
            return bool(val)

    def get_int(self, key: str, default: int = 0) -> int:
        """Get a parameter as int. Handles: '30', Decimal(30), 30.0."""
        val = self.get_parameter(key, default)
        try:
            return int(val)
        except (TypeError, ValueError):
            return default

    def get_str(self, key: str, default: str = '') -> str:
        """Get a parameter as string."""
        val = self.get_parameter(key, default)
        return str(val) if val is not None else default

    @abstractmethod
    def create_infrastructure(self) -> Dict[str, Any]:
        """Create the complete infrastructure"""
        pass
    
    @abstractmethod
    def get_outputs(self) -> Dict[str, Any]:
        """Get the outputs that this template provides"""
        pass
    
    @classmethod
    def get_metadata(cls) -> TemplateMetadata:
        """Get metadata for this template"""
        pass

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        """Get configuration schema for the UI"""
        return {}
    
    def validate_config(self) -> bool:
        """Validate the template configuration"""
        return True
    
    def get_estimated_cost(self) -> str:
        """Get estimated monthly cost for this template"""
        metadata = self.get_metadata()
        return metadata.estimated_cost
    
    def get_deployment_time(self) -> str:
        """Get estimated deployment time"""
        metadata = self.get_metadata()
        return metadata.deployment_time
    
    def get_resource_tags(self) -> Dict[str, str]:
        """Get common tags for all resources in this template"""
        return {
            "Template": self.name,
            "Category": self.get_metadata().category.value,
            "ManagedBy": "Pulumi",
            "Environment": self.config.get("environment", "development"),
            "Project": self.config.get("project_name", "archie-generated")
        }


class TemplateRegistry:
    """
    Registry for infrastructure templates
    
    Manages registration and discovery of available templates.
    """
    
    _templates: Dict[str, Type[InfrastructureTemplate]] = {}
    
    @classmethod
    def register(cls, template_name: str, template_class: Type[InfrastructureTemplate]) -> None:
        """Register a template"""
        cls._templates[template_name] = template_class
    
    @classmethod
    def get_template(cls, template_name: str) -> Optional[Type[InfrastructureTemplate]]:
        """Get a template by name"""
        return cls._templates.get(template_name)
    
    @classmethod
    def list_templates(cls) -> List[str]:
        """List all registered templates"""
        return list(cls._templates.keys())
    
    @classmethod
    def get_template_metadata(cls, template_name: str) -> Optional[TemplateMetadata]:
        """Get metadata for a template"""
        template_class = cls.get_template(template_name)
        if template_class:
            return template_class.get_metadata()
        return None
    
    @classmethod
    def search_templates(
        cls, 
        category: TemplateCategory = None,
        tags: List[str] = None, 
        max_complexity: str = None,
        supported_region: str = None
    ) -> List[str]:
        """Search templates by various criteria"""
        matching_templates = []
        complexity_order = ["low", "medium", "high", "very_high"]
        
        for template_name, template_class in cls._templates.items():
            metadata = template_class.get_metadata()
            
            # Check category
            if category and metadata.category != category:
                continue
            
            # Check tags
            if tags and not any(tag in metadata.tags for tag in tags):
                continue
            
            # Check complexity
            if max_complexity:
                template_complexity_idx = complexity_order.index(metadata.complexity)
                max_complexity_idx = complexity_order.index(max_complexity)
                if template_complexity_idx > max_complexity_idx:
                    continue
            
            # Check region support
            if supported_region and supported_region not in metadata.supported_regions:
                continue
            
            matching_templates.append(template_name)
        
        return matching_templates
    
    @classmethod
    def get_templates_by_category(cls, category: TemplateCategory) -> List[str]:
        """Get all templates in a specific category"""
        return cls.search_templates(category=category)
    
    @classmethod
    def get_popular_templates(cls, limit: int = 10) -> List[str]:
        """Get most popular templates (placeholder - could be based on usage stats)"""
        # For now, return templates sorted alphabetically
        # In production, this could be based on actual usage metrics
        templates = cls.list_templates()
        return sorted(templates)[:limit]


def template_registry(name: str):
    """
    Decorator for registering templates
    
    Usage:
        @template_registry("vpc_production")
        class VpcProductionTemplate(InfrastructureTemplate):
            ...
    """
    def decorator(cls: Type[InfrastructureTemplate]) -> Type[InfrastructureTemplate]:
        TemplateRegistry.register(name, cls)
        return cls
    return decorator


class TemplateComposer:
    """
    Template composer for dynamic template creation
    
    Helps create templates programmatically by combining modules.
    """
    
    def __init__(self):
        self.modules = []
        self.config = {}
        self.metadata = None
    
    def add_module(self, module_name: str, module_config: Dict[str, Any]) -> 'TemplateComposer':
        """Add a module to the template"""
        self.modules.append({
            "name": module_name,
            "config": module_config
        })
        return self
    
    def set_config(self, config: Dict[str, Any]) -> 'TemplateComposer':
        """Set template configuration"""
        self.config = config
        return self
    
    def set_metadata(self, metadata: TemplateMetadata) -> 'TemplateComposer':
        """Set template metadata"""
        self.metadata = metadata
        return self
    
    def build(self) -> Dict[str, Any]:
        """Build the template configuration"""
        template_config = {
            "name": self.metadata.name if self.metadata else "dynamic-template",
            "description": self.metadata.description if self.metadata else "Dynamically generated template",
            "modules": self.modules,
            "config": self.config
        }
        
        if self.metadata:
            template_config["metadata"] = {
                "category": self.metadata.category.value,
                "version": self.metadata.version,
                "author": self.metadata.author,
                "tags": self.metadata.tags,
                "estimated_cost": self.metadata.estimated_cost,
                "complexity": self.metadata.complexity,
                "deployment_time": self.metadata.deployment_time
            }
        
        return template_config
