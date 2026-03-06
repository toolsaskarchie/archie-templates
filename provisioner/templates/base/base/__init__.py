"""Base template configuration classes and infrastructure template base."""
from .config import TemplateConfig
from .template import (
    InfrastructureTemplate,
    TemplateMetadata,
    TemplateCategory,
    TemplateRegistry,
    TemplateComposer,
    template_registry
)

__all__ = [
    'TemplateConfig',
    'InfrastructureTemplate',
    'TemplateMetadata',
    'TemplateCategory',
    'TemplateRegistry',
    'TemplateComposer',
    'template_registry'
]
