"""
YAML Catalog Loader and Parser

Loads and validates resource, template, and solution definitions from YAML files.
"""

import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass


@dataclass
class ResourceDefinition:
    """Represents a catalog resource definition"""
    name: str
    category: str
    provider: str
    description: str
    parameters: Dict[str, Any]
    outputs: Dict[str, Any]
    iac_mappings: Dict[str, str]
    cost_tier: str
    metadata: Dict[str, Any]
    raw_yaml: Dict[str, Any]


@dataclass
class TemplateDefinition:
    """Represents a template definition"""
    name: str
    display_name: str
    category: str
    provider: str
    description: str
    resources: List[str]
    parameters: Dict[str, Any]
    outputs: Dict[str, Any]
    cost_estimate: Dict[str, Any]
    tags: List[str]
    supported_iaas: List[str]
    metadata: Dict[str, Any]
    raw_yaml: Dict[str, Any]


@dataclass
class SolutionDefinition:
    """Represents a solution definition"""
    name: str
    display_name: str
    description: str
    templates: List[str]
    parameters: Dict[str, Any]
    outputs: Dict[str, Any]
    metadata: Dict[str, Any]
    raw_yaml: Dict[str, Any]


class CatalogLoader:
    """Loads and caches YAML catalog definitions"""
    
    def __init__(self, catalog_root: Path):
        """
        Initialize catalog loader
        
        Args:
            catalog_root: Root path to catalog/ directory
        """
        self.catalog_root = catalog_root
        self._resource_cache: Dict[str, ResourceDefinition] = {}
        self._template_cache: Dict[str, TemplateDefinition] = {}
        self._solution_cache: Dict[str, SolutionDefinition] = {}
    
    def load_resource(self, provider: str, category: str, resource_name: str) -> ResourceDefinition:
        """
        Load resource definition from catalog
        
        Args:
            provider: Cloud provider (aws, azure, gcp)
            category: Resource category (networking, compute, storage, etc.)
            resource_name: Resource name (vpc, subnet, ec2, etc.)
        
        Returns:
            ResourceDefinition: Parsed resource definition
        
        Example:
            >>> loader = CatalogLoader(Path("provisioner/catalog"))
            >>> vpc = loader.load_resource("aws", "networking", "vpc")
            >>> vpc.iac_mappings["pulumi"]
            "aws.ec2.Vpc"
        """
        cache_key = f"{provider}/{category}/{resource_name}"
        
        if cache_key in self._resource_cache:
            return self._resource_cache[cache_key]
        
        yaml_path = self.catalog_root / provider / category / f"{resource_name}.yaml"
        
        if not yaml_path.exists():
            raise FileNotFoundError(f"Resource definition not found: {yaml_path}")
        
        with open(yaml_path, 'r') as f:
            data = yaml.safe_load(f)
        
        resource = ResourceDefinition(
            name=data.get("name", resource_name),
            category=data.get("category", category),
            provider=data.get("provider", provider),
            description=data.get("description", ""),
            parameters=data.get("parameters", {}),
            outputs=data.get("outputs", {}),
            iac_mappings=data.get("iac_mappings", {}),
            cost_tier=data.get("cost", {}).get("tier", "unknown"),
            metadata=data.get("metadata", {}),
            raw_yaml=data
        )
        
        self._resource_cache[cache_key] = resource
        return resource
    
    def load_template(self, template_path: Path) -> TemplateDefinition:
        """
        Load template definition from template.yaml
        
        Args:
            template_path: Path to template directory containing template.yaml
        
        Returns:
            TemplateDefinition: Parsed template definition
        
        Example:
            >>> loader = CatalogLoader(Path("provisioner/catalog"))
            >>> template = loader.load_template(Path("templates/aws/networking/vpc_nonprod"))
            >>> template.supported_iaas
            ["pulumi", "terraform"]
        """
        yaml_path = template_path / "template.yaml"
        
        cache_key = str(template_path)
        if cache_key in self._template_cache:
            return self._template_cache[cache_key]
        
        if not yaml_path.exists():
            raise FileNotFoundError(f"Template definition not found: {yaml_path}")
        
        with open(yaml_path, 'r') as f:
            data = yaml.safe_load(f)
        
        template = TemplateDefinition(
            name=data.get("name", template_path.name),
            display_name=data.get("display_name", ""),
            category=data.get("category", ""),
            provider=data.get("provider", ""),
            description=data.get("description", ""),
            resources=data.get("resources", []),
            parameters=data.get("parameters", {}),
            outputs=data.get("outputs", {}),
            cost_estimate=data.get("cost_estimate", {}),
            tags=data.get("tags", []),
            supported_iaas=data.get("supported_iaas", ["pulumi"]),
            metadata=data.get("metadata", {}),
            raw_yaml=data
        )
        
        self._template_cache[cache_key] = template
        return template
    
    def load_solution(self, solution_path: Path) -> SolutionDefinition:
        """
        Load solution definition from solution.yaml
        
        Args:
            solution_path: Path to solution directory containing solution.yaml
        
        Returns:
            SolutionDefinition: Parsed solution definition
        """
        yaml_path = solution_path / "solution.yaml"
        
        cache_key = str(solution_path)
        if cache_key in self._solution_cache:
            return self._solution_cache[cache_key]
        
        if not yaml_path.exists():
            raise FileNotFoundError(f"Solution definition not found: {yaml_path}")
        
        with open(yaml_path, 'r') as f:
            data = yaml.safe_load(f)
        
        solution = SolutionDefinition(
            name=data.get("name", solution_path.name),
            display_name=data.get("display_name", ""),
            description=data.get("description", ""),
            templates=data.get("templates", []),
            parameters=data.get("parameters", {}),
            outputs=data.get("outputs", {}),
            metadata=data.get("metadata", {}),
            raw_yaml=data
        )
        
        self._solution_cache[cache_key] = solution
        return solution
    
    def list_resources(self, provider: Optional[str] = None, category: Optional[str] = None) -> List[Path]:
        """
        List all resource YAML files in catalog
        
        Args:
            provider: Optional provider filter (aws, azure, gcp)
            category: Optional category filter (networking, compute, etc.)
        
        Returns:
            List[Path]: List of resource YAML file paths
        """
        if provider and category:
            search_path = self.catalog_root / provider / category
            if not search_path.exists():
                return []
            return list(search_path.glob("*.yaml"))
        elif provider:
            search_path = self.catalog_root / provider
            if not search_path.exists():
                return []
            return list(search_path.glob("*/*.yaml"))
        else:
            return list(self.catalog_root.glob("*/*/*.yaml"))
    
    def list_templates(self, templates_root: Path, provider: Optional[str] = None) -> List[Path]:
        """
        List all template directories containing template.yaml
        
        Args:
            templates_root: Root path to templates/ directory
            provider: Optional provider filter (aws, azure, gcp)
        
        Returns:
            List[Path]: List of template directory paths
        """
        if provider:
            search_path = templates_root / provider
            if not search_path.exists():
                return []
            return [p.parent for p in search_path.glob("*/*/template.yaml")]
        else:
            return [p.parent for p in templates_root.glob("*/*/*/template.yaml")]
    
    def validate_resource(self, resource: ResourceDefinition) -> List[str]:
        """
        Validate resource definition
        
        Args:
            resource: Resource definition to validate
        
        Returns:
            List[str]: List of validation errors (empty if valid)
        """
        errors = []
        
        if not resource.name:
            errors.append("Resource name is required")
        
        if not resource.provider:
            errors.append("Resource provider is required")
        
        if not resource.iac_mappings:
            errors.append("At least one IaC mapping is required")
        
        # Validate parameters have required fields
        for param_name, param_def in resource.parameters.items():
            if not isinstance(param_def, dict):
                errors.append(f"Parameter {param_name} must be a dictionary")
                continue
            
            if "type" not in param_def:
                errors.append(f"Parameter {param_name} missing type")
            
            if "description" not in param_def:
                errors.append(f"Parameter {param_name} missing description")
        
        # Validate outputs have required fields
        for output_name, output_def in resource.outputs.items():
            if not isinstance(output_def, dict):
                errors.append(f"Output {output_name} must be a dictionary")
                continue
            
            if "type" not in output_def:
                errors.append(f"Output {output_name} missing type")
        
        return errors
    
    def validate_template(self, template: TemplateDefinition) -> List[str]:
        """
        Validate template definition
        
        Args:
            template: Template definition to validate
        
        Returns:
            List[str]: List of validation errors (empty if valid)
        """
        errors = []
        
        if not template.name:
            errors.append("Template name is required")
        
        if not template.provider:
            errors.append("Template provider is required")
        
        if not template.resources:
            errors.append("Template must reference at least one resource")
        
        if not template.supported_iaas:
            errors.append("Template must support at least one IaC tool")
        
        # Validate parameters
        for param_name, param_def in template.parameters.items():
            if not isinstance(param_def, dict):
                errors.append(f"Parameter {param_name} must be a dictionary")
                continue
            
            if "type" not in param_def:
                errors.append(f"Parameter {param_name} missing type")
        
        return errors
    
    def get_resource_iac_type(self, resource: ResourceDefinition, iac_tool: str) -> Optional[str]:
        """
        Get the IaC-specific resource type for a resource
        
        Args:
            resource: Resource definition
            iac_tool: IaC tool (pulumi, terraform, cloudformation)
        
        Returns:
            Optional[str]: IaC-specific type (e.g., "aws.ec2.Vpc") or None if not supported
        """
        return resource.iac_mappings.get(iac_tool)
    
    def clear_cache(self):
        """Clear all cached definitions"""
        self._resource_cache.clear()
        self._template_cache.clear()
        self._solution_cache.clear()
