"""
Create basic website infrastructure — Archie Template
Generated stub — enable Bedrock for full AI generation.
"""
from typing import Any, Dict, Optional
from pathlib import Path
import pulumi

from provisioner.utils.aws import ResourceNamer
from provisioner.utils.aws.tags import get_standard_tags
from provisioner.templates.base import template_registry, InfrastructureTemplate
from provisioner.templates.template_config import TemplateConfig
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory


@template_registry("aws-create-basic-website-infrastructure-nonprod")
class GeneratedTemplate(InfrastructureTemplate):
    """Generated template stub — enable Bedrock for full implementation."""

    def __init__(self, name: str = None, config: Dict[str, Any] = None, **kwargs):
        raw_config = config or kwargs or {}
        if name is None:
            name = raw_config.get('project_name', 'create-basic-website-infrastructure')
        super().__init__(name, raw_config)
        template_dir = Path(__file__).parent
        self.cfg = TemplateConfig(template_dir, raw_config)

    def create_infrastructure(self) -> Dict[str, Any]:
        return self.create()

    def create(self) -> Dict[str, Any]:
        environment = self.cfg.get('environment', 'nonprod')
        tags = get_standard_tags(
            project=self.cfg.project_name,
            environment=environment,
            template="aws-create-basic-website-infrastructure"
        )
        # TODO: AI-generated resources will go here when Bedrock is enabled
        return self.get_outputs()

    def get_outputs(self) -> Dict[str, Any]:
        return {"project_name": self.name}

    @classmethod
    def get_metadata(cls) -> Dict[str, Any]:
        return {
            "name": "aws-create-basic-website-infrastructure-nonprod",
            "title": "Create basic website infrastructure",
            "description": "Create basic website infrastructure",
            "category": "compute",
            "version": "1.0.0",
            "author": "AskArchie",
            "cloud": "aws",
            "environment": "nonprod",
            "deployment_time": "3-5 minutes",
            "complexity": "medium"
        }

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "required": ["project_name", "region"]
        }
