"""
Composed: Application Load Balancer + CloudFront CDN — Composed Archie Stack
Combines: Application Load Balancer, CloudFront CDN
Enable Bedrock for full AI-powered composition with cross-template wiring.
"""
from typing import Any, Dict
from pathlib import Path
import pulumi
import pulumi_aws as aws

from provisioner.utils.aws import ResourceNamer
from provisioner.utils.aws.tags import get_standard_tags
from provisioner.templates.base import template_registry, InfrastructureTemplate
from provisioner.templates.template_config import TemplateConfig
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory


@template_registry("aws-alb-cdn-group")
class ComposedStackTemplate(InfrastructureTemplate):
    """
    Composed: Application Load Balancer + CloudFront CDN

    Composed from: Application Load Balancer, CloudFront CDN
    Enable Bedrock for full resource wiring and cross-template integration.
    """

    def __init__(self, name: str = None, config: Dict[str, Any] = None, **kwargs):
        raw_config = config or kwargs or {}
        if name is None:
            name = raw_config.get('project_name', 'alb-cdn-group')
        super().__init__(name, raw_config)
        template_dir = Path(__file__).parent
        self.cfg = TemplateConfig(template_dir, raw_config)

    def create_infrastructure(self) -> Dict[str, Any]:
        return self.create()

    def create(self) -> Dict[str, Any]:
        environment = self.cfg.get('environment', 'prod')
        tags = get_standard_tags(
            project=self.cfg.project_name,
            environment=environment,
            template="aws-alb-cdn-group"
        )

        # LoadBalancer resource
        self.alb_aws_name = factory.create("aws:lb:LoadBalancer", f"{self.name}-alb_aws_name", tags=tags)

        # TargetGroup resource
        self.tg_name = factory.create("aws:lb:TargetGroup", f"{self.name}-tg_name", tags=tags)

        # Security group for backend instances
        self.secg_backend_project_environment_region_short = factory.create("aws:ec2:SecurityGroup", f"{self.name}-secg-backend-project-environment-region_short", tags=tags)

        # SecurityGroupRule resource
        self.project_name_alb_to_target = factory.create("aws:ec2:SecurityGroupRule", f"{self.name}-project_name-alb-to-target", tags=tags)

        # Listener resource
        self.project_name_http = factory.create("aws:lb:Listener", f"{self.name}-project_name-http", tags=tags)

        # TargetGroupAttachment resource
        self.project_name_attachment_ = factory.create("aws:lb:TargetGroupAttachment", f"{self.name}-project_name-attachment-", tags=tags)

        # Listener resource
        self.project_name_https = factory.create("aws:lb:Listener", f"{self.name}-project_name-https", tags=tags)

        # Role resource
        self.role_service_project_environment_region_short = factory.create("aws:iam:Role", f"{self.name}-role-service-project-environment-region_short", tags=tags)

        # InstanceProfile resource
        self.iam_profile = factory.create("aws:iam:InstanceProfile", f"{self.name}-iam_profile", tags=tags)

        # Instance resource
        self.ec2_preset_project_environment_region_short = factory.create("aws:ec2:Instance", f"{self.name}-ec2-preset-project-environment-region_short", tags=tags)

        return self.get_outputs()

    def get_outputs(self) -> Dict[str, Any]:
        return {"project_name": self.name}

    @classmethod
    def get_metadata(cls) -> Dict[str, Any]:
        return {
            "name": "aws-alb-cdn-group",
            "title": "Composed: Application Load Balancer + CloudFront CDN",
            "description": "Composed stack combining Application Load Balancer, CloudFront CDN.",
            "category": "compute",
            "version": "1.0.0",
            "cloud": "aws",
            "environment": "prod",
            "deployment_time": "5-10 minutes",
            "complexity": "advanced"
        }

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "required": ["project_name", "region"]
        }
