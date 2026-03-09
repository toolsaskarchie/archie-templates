"""
Composed: Enterprise Application Load Balancer + Aurora Database Cluster — Composed Archie Stack
Combines: Enterprise Application Load Balancer, Aurora Database Cluster
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


@template_registry("aws-alb-aurora")
class ComposedStackTemplate(InfrastructureTemplate):
    """
    Composed: Enterprise Application Load Balancer + Aurora Database Cluster

    Composed from: Enterprise Application Load Balancer, Aurora Database Cluster
    Enable Bedrock for full resource wiring and cross-template integration.
    """

    def __init__(self, name: str = None, config: Dict[str, Any] = None, **kwargs):
        raw_config = config or kwargs or {}
        if name is None:
            name = raw_config.get('project_name', 'alb-aurora')
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
            template="aws-alb-aurora"
        )

        # Application Load Balancer distributing traffic across backend instances in multiple availability zones
        self.alb_{project}_{environment}_{region_short} = factory.create("aws:lb:LoadBalancer", f"{self.name}-alb-{project}-{environment}-{region_short}", tags=tags)

        # Target group routing traffic to backend EC2 instances on port 80
        self.tg_{project}_{environment}_{region_short} = factory.create("aws:lb:TargetGroup", f"{self.name}-tg-{project}-{environment}-{region_short}", tags=tags)

        # Security group for ALB allowing HTTP/HTTPS traffic from internet
        self.secg_alb_{project}_{environment}_{region_short} = factory.create("aws:ec2:SecurityGroup", f"{self.name}-secg-alb-{project}-{environment}-{region_short}", tags=tags)

        # Security group for backend instances accepting traffic only from ALB
        self.secg_backend_{project}_{environment}_{region_short} = factory.create("aws:ec2:SecurityGroup", f"{self.name}-secg-backend-{project}-{environment}-{region_short}", tags=tags)

        # HTTP listener on port 80 forwarding traffic to target group
        self.listener_http_{project}_{environment} = factory.create("aws:lb:Listener", f"{self.name}-listener-http-{project}-{environment}", tags=tags)

        # HTTPS listener on port 443 with ACM certificate
        self.listener_https_{project}_{environment} = factory.create("aws:lb:Listener", f"{self.name}-listener-https-{project}-{environment}", tags=tags)

        # Target group attachment connecting EC2 instances to load balancer
        self.attachment_{instance_name}_{project}_{environment} = factory.create("aws:lb:TargetGroupAttachment", f"{self.name}-attachment-{instance_name}-{project}-{environment}", tags=tags)

        # Virtual Private Cloud with CIDR {config_custom_cidr_block}, DNS support enabled
        self.vpc_{project}_{environment}_{region_short}_{network_num} = factory.create("aws:ec2:Vpc", f"{self.name}-vpc-{project}-{environment}-{region_short}-{network_num}", tags=tags)

        # Internet Gateway providing public internet connectivity for the VPC
        self.igw_main_{project}_{environment}_{region_short} = factory.create("aws:ec2:InternetGateway", f"{self.name}-igw-main-{project}-{environment}-{region_short}", tags=tags)

        # Route table for public tier network traffic routing
        self.rt_public_{project}_{environment}_{region_short} = factory.create("aws:ec2:RouteTable", f"{self.name}-rt-public-{project}-{environment}-{region_short}", tags=tags)

        return self.get_outputs()

    def get_outputs(self) -> Dict[str, Any]:
        return {"project_name": self.name}

    @classmethod
    def get_metadata(cls) -> Dict[str, Any]:
        return {
            "name": "aws-alb-aurora",
            "title": "Composed: Enterprise Application Load Balancer + Aurora Database Cluster",
            "description": "Composed stack combining Enterprise Application Load Balancer, Aurora Database Cluster.",
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
