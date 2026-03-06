"""
Atomic template base classes

Provides base classes for atomic templates with pydantic config support.
"""

from typing import Dict, Any
from abc import ABC, abstractmethod
from pydantic import BaseModel
from provisioner.templates.base import template_registry


class AtomicConfig(BaseModel):
    """Base configuration class for atomic templates using pydantic"""
    
    class Config:
        extra = "allow"  # Allow additional fields
        arbitrary_types_allowed = True


class AtomicTemplate(ABC):
    """
    Base class for atomic templates
    
    Atomic templates create single resources or small resource groups.
    They are lightweight and don't require full InfrastructureTemplate overhead.
    """
    
    def __init__(self, name: str, config: Dict[str, Any], **kwargs):
        self.name = name
        self.config = config
        self.resource_options = kwargs.get('resource_options', None)
        self.outputs = {}
    
    @abstractmethod
    def create_infrastructure(self) -> Dict[str, Any]:
        """Create the infrastructure resources"""
        pass
    
    @abstractmethod
    def get_outputs(self) -> Dict[str, Any]:
        """Get the outputs from this atomic template"""
        pass
    
    @abstractmethod
    def get_metadata(self) -> Dict[str, Any]:
        """Get metadata for this atomic template"""
        pass


__all__ = ['AtomicTemplate', 'AtomicConfig', 'template_registry']
