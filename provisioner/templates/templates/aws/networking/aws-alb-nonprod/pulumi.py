"""
AWS ALB Non-Production Template

Composes:
1. VPC Non-Prod (Layer 4 template)
2. EC2 Non-Prod (Layer 4 template)
3. ALB Components (ALB, Target Group, Listeners) via PulumiAtomicFactory
"""
from typing import Any, Dict, Optional, List
from pathlib import Path

import pulumi
import pulumi_aws as aws

from provisioner.templates.base import (
    InfrastructureTemplate,
    template_registry
)
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory
from provisioner.templates.template_config import TemplateConfig
from provisioner.utils.aws import ResourceNamer, get_standard_tags
from provisioner.utils.aws.naming import sanitize_name
from provisioner.templates.templates.aws.networking.alb_nonprod.config import ALBNonProdConfig
from provisioner.templates.templates.aws.networking.vpc_prod.pulumi import VPCProdTemplate
from provisioner.templates.templates.aws.compute.ec2_nonprod.pulumi import EC2NonProdTemplate


@template_registry("aws-alb-nonprod")
class ALBNonProdTemplate(InfrastructureTemplate):
    """
    AWS Application Load Balancer Non-Prod Template
    """
    def __init__(self, name: str = None, config: Dict[str, Any] = None, **kwargs):
        """Initialize ALB nonprod template"""
        raw_config = config or kwargs or {}
        
        if name is None:
            name = raw_config.get('project_name', raw_config.get('projectName', 'alb-nonprod'))
            
        # Sanitize name for AWS ALB (no underscores allowed, 32 char limit)
        name = sanitize_name(name, 32)
        super().__init__(name, raw_config)
        
        # Load template configuration (Pattern B)
        template_dir = Path(__file__).parent
        self.config_loader = TemplateConfig(template_dir, raw_config)
        self.cfg = ALBNonProdConfig(raw_config)
        
        # Sub-templates
        self.vpc_template: Optional[VPCProdTemplate] = None
        self.ec2_templates: List[EC2NonProdTemplate] = []
        
        # Resources (Pattern B)
        self.alb = None
        self.target_group = None
        self.listeners = []
        self.security_groups = []
        self.target_group_attachments = []
        self.ssl_certificate = None

    def create_infrastructure(self) -> Dict[str, Any]:
        # Config values nested in parameters — check both levels (Rule #6)
        params = self.config.get('parameters', {})
        def cfg(key, default=None):
            return self.config.get(key) or params.get(key) or default

        """Deploy infrastructure (implements abstract method)"""
        return self.create()

    def create(self) -> Dict[str, Any]:
        """Deploy ALB infrastructure using factory pattern"""
        # Initialize ResourceNamer
        namer = ResourceNamer(
            project=self.cfg.project_name,
            environment=self.cfg.environment,
            region=self.cfg.region,
            template="aws-alb-nonprod"
        )
        
        # Generate standard tags
        tags = get_standard_tags(
            project=self.cfg.project_name,
            environment=self.cfg.environment,
            template="alb-nonprod"
        )
        tags.update(self.cfg.tags)

        # ========================================
        # STEP 1: VPC PROVISIONING
        # ========================================
        vpc_id = None
        public_subnet_ids = []
        private_subnet_ids = []
        alb_sg_id = None
        
        if self.cfg.vpc_mode == 'new':
            # Pass ALL parent config to VPC (includes injected upgrade outputs)
            # Override only what the child specifically needs different
            vpc_config = {**(self.config if isinstance(self.config, dict) else {})}
            if 'parameters' in vpc_config:
                vpc_config.update(vpc_config.pop('parameters'))
            vpc_config["project_name"] = f"{self.name}-vpc"
            vpc_config["cidr_block"] = self.cfg.vpc_cidr
            vpc_config["environment"] = self.cfg.environment
            vpc_config["ssh_access_ip"] = self.cfg.ssh_access_ip or ''
            vpc_config["app_sg_allow_from_web"] = True
            vpc_config["app_sg_port"] = self.cfg.target_port
            self.vpc_template = VPCProdTemplate(name=f"{self.name}-vpc", config=vpc_config)
            self.vpc_template.create_infrastructure()
            vpc_outputs = self.vpc_template.get_outputs()
            
            vpc_id = vpc_outputs['vpc_id']
            public_subnet_ids = vpc_outputs['public_subnet_ids']
            private_subnet_ids = vpc_outputs['private_subnet_ids']
            alb_sg_id = vpc_outputs.get('web_security_group_id')
        else:
            vpc_id = self.cfg.vpc_id
            public_subnet_ids = self.get_parameter('public_subnet_ids', [])
            private_subnet_ids = self.get_parameter('private_subnet_ids', public_subnet_ids)

        # ========================================
        # STEP 2: SSL CERTIFICATE
        # ========================================
        certificate_arn = self.cfg.certificate_arn
        if not certificate_arn and self.cfg.enable_https:
            # Create self-signed certificate for non-prod
            cert_name = namer.resource("acm-cert")
            self.ssl_certificate = factory.create(
                "aws:acm:Certificate",
                cert_name,
                domain_name=f"*.{self.cfg.project_name}.local",
                validation_method="DNS",
                tags={**tags, "Name": cert_name}
            )
            certificate_arn = self.ssl_certificate.arn

        # ========================================
        # STEP 3: SECURITY GROUPS
        # ========================================
        if not alb_sg_id:
            # Create dedicated ALB SG
            sg_name = namer.security_group(purpose="alb", ports=[80, 443])
            alb_sg = factory.create(
                "aws:ec2:SecurityGroup",
                sg_name,
                vpc_id=vpc_id,
                description="ALB Security Group",
                ingress=[
                    {"protocol": "tcp", "from_port": 80, "to_port": 80, "cidr_blocks": self.cfg.allowed_ips, "description": "HTTP access"},
                    {"protocol": "tcp", "from_port": 443, "to_port": 443, "cidr_blocks": self.cfg.allowed_ips, "description": "HTTPS access"}
                ],
                egress=[{"protocol": "-1", "from_port": 0, "to_port": 0, "cidr_blocks": ["0.0.0.0/0"]}],
                tags={**tags, "Name": sg_name}
            )
            self.security_groups.append(alb_sg)
            alb_sg_id = alb_sg.id

        # Target Security Group (backend instances)
        # When vpc_mode='new', the VPC template creates the app SG with inline ingress
        # (we passed app_sg_allow_from_web=True above). No separate SecurityGroupRule needed.
        target_sg_id = None
        if self.cfg.vpc_mode == 'new' and self.vpc_template:
            vpc_outputs = self.vpc_template.get_outputs()
            target_sg_id = vpc_outputs.get('app_security_group_id')
        
        if not target_sg_id:
            sg_name = namer.security_group(purpose="backend", ports=[self.cfg.target_port])
            target_sg = factory.create(
                "aws:ec2:SecurityGroup",
                sg_name,
                vpc_id=vpc_id,
                description="Security group for backend instances",
                ingress=[{
                    "protocol": "tcp",
                    "from_port": self.cfg.target_port,
                    "to_port": self.cfg.target_port,
                    "source_security_group_id": alb_sg_id,
                    "description": "Traffic from ALB"
                }],
                egress=[{"protocol": "-1", "from_port": 0, "to_port": 0, "cidr_blocks": ["0.0.0.0/0"]}],
                tags={**tags, "Name": sg_name}
            )
            self.security_groups.append(target_sg)
            target_sg_id = target_sg.id

        # ========================================
        # STEP 4: COMPUTE (BACKEND INSTANCES)
        # ========================================
        instance_ids = []
        # Letter suffixes avoid _clean_project_name stripping numeric tokens
        _az_labels = ["alpha", "bravo", "charlie", "delta", "echo", "foxtrot"]
        for i in range(self.cfg.ec2_instance_count):
            subnet_id = private_subnet_ids[i % len(private_subnet_ids)] if private_subnet_ids else None
            label = _az_labels[i] if i < len(_az_labels) else f"node{i}"
            ec2_config = {
                "parameters": {
                    "aws": {
                        "project_name": f"{self.name}-{label}",
                        "environment": self.cfg.environment,
                        "vpcId": vpc_id,
                        "subnetId": subnet_id,
                        "vpcMode": "existing",
                        "instanceType": self.cfg.ec2_instance_type,
                        "securityGroupIds": [target_sg_id] if target_sg_id else [],
                        "configPreset": "alb-backend",
                        "ssh_access_ip": self.cfg.ssh_access_ip or '',
                    }
                }
            }
            ec2_template = EC2NonProdTemplate(name=f"{self.name}-{label}", config=ec2_config)
            ec2_template.create_infrastructure()
            self.ec2_templates.append(ec2_template)
            instance_ids.append(ec2_template.get_outputs().get('instance_id'))

        # ========================================
        # STEP 5: LOAD BALANCER
        # ========================================
        alb_aws_name = (cfg('alb_resource_name') or self.config.get('parameters', {}).get('alb_resource_name')) or sanitize_name(self.name, 24)
        self.alb = factory.create(
            "aws:lb:LoadBalancer",
            alb_aws_name,
            load_balancer_type="application",
            subnets=public_subnet_ids,
            security_groups=[alb_sg_id],
            internal=self.cfg.internal,
            tags={**tags, "Name": alb_aws_name},
        )

        # ========================================
        # STEP 6: TARGET GROUP
        # ========================================
        # Reuse existing TG name on upgrade/remediate to avoid destroy+create
        params = self.config.get('parameters', {})
        existing_tg_name = cfg('target_group_name') or params.get('target_group_name') or ''
        tg_name = existing_tg_name or sanitize_name(f"tg-{namer.project}-nonprod", 24)
        self.target_group = factory.create(
            "aws:lb:TargetGroup",
            tg_name,
            port=self.cfg.target_port,
            protocol=self.cfg.target_protocol,
            vpc_id=vpc_id,
            target_type="instance",
            health_check={
                "enabled": True,
                "path": "/",
                "interval": 30,
                "timeout": 5,
                "healthy_threshold": 2,
                "unhealthy_threshold": 2,
            },
            tags={**tags, "Name": tg_name},
        )

        # ========================================
        # STEP 7: LISTENERS
        # ========================================
        # HTTP Listener
        http_listener_name = (cfg('http_listener_name') or self.config.get('parameters', {}).get('http_listener_name')) or f"{alb_aws_name}-http"
        self.listeners.append(factory.create(
            "aws:lb:Listener",
            http_listener_name,
            load_balancer_arn=self.alb.arn,
            port=80,
            protocol="HTTP",
            default_actions=[{
                "type": "forward",
                "target_group_arn": self.target_group.arn
            }]
        ))

        # HTTPS Listener
        if self.cfg.enable_https and certificate_arn:
            https_listener_name = (cfg('https_listener_name') or self.config.get('parameters', {}).get('https_listener_name')) or f"{alb_aws_name}-https"
            self.listeners.append(factory.create(
                "aws:lb:Listener",
                https_listener_name,
                load_balancer_arn=self.alb.arn,
                port=443,
                protocol="HTTPS",
                certificate_arn=certificate_arn,
                default_actions=[{
                    "type": "forward",
                    "target_group_arn": self.target_group.arn
                }]
            ))

        # ========================================
        # STEP 8: ATTACHMENTS
        # ========================================
        for i, instance_id in enumerate(instance_ids):
            attachment = factory.create(
                "aws:lb:TargetGroupAttachment",
                f"{self.name}-attachment-{i+1}",
                target_group_arn=self.target_group.arn,
                target_id=instance_id,
                port=self.cfg.target_port
            )
            self.target_group_attachments.append(attachment)

        # Exports
        pulumi.export("alb_dns_name", self.alb.dns_name)
        pulumi.export("alb_arn", self.alb.arn)
        pulumi.export("alb_resource_name", alb_aws_name)
        pulumi.export("http_listener_name", http_listener_name)
        pulumi.export("target_group_arn", self.target_group.arn)
        pulumi.export("target_group_name", tg_name)
        pulumi.export("alb_url", pulumi.Output.concat("http://", self.alb.dns_name))
        if certificate_arn:
            pulumi.export("certificate_arn", certificate_arn)
        if self.cfg.enable_https:
            pulumi.export("https_url", pulumi.Output.concat("https://", self.alb.dns_name))
        if vpc_id:
            pulumi.export("vpc_id", vpc_id)

        return self.get_outputs()

    def get_outputs(self) -> Dict[str, Any]:
        """Get template outputs (Pattern B)"""
        if not self.alb:
            return {"status": "not_created"}

        outputs = {
            "alb_dns_name": self.alb.dns_name,
            "alb_arn": self.alb.arn,
            "target_group_arn": self.target_group.arn if self.target_group else None
        }
        
        if self.ssl_certificate:
            outputs["certificate_arn"] = self.ssl_certificate.arn
            
        if self.vpc_template:
            outputs.update(self.vpc_template.get_outputs())
            
        return outputs

    @classmethod
    def get_metadata(cls) -> Dict[str, Any]:
        """Pattern B Metadata source of truth"""
        return {
            "name": "aws-alb-nonprod",
            "title": "Application Load Balancer",
            "description": "Complete web architecture featuring a highly available ALB distributing traffic to EC2 backend instances with SSL certificate support.",
            "category": "networking",
            "version": "1.3.0",
            "author": "InnovativeApps",
            "cloud": "aws",
            "environment": "nonprod",
            "base_cost": "$45/month",
            "features": [
                "Dedicated Multi-AZ VPC Architecture",
                "Automated EC2 Backend fleet provisioning",
                "Security Group isolation tiers (ALB vs App)",
                "Integrated Health Checks & Target Management",
                "HTTPS support with ACM integration",
                "Auto-generated SSL certificates for non-prod environments"
            ],
            "tags": ["alb", "load-balancer", "ha", "networking", "nonprod", "ssl"],
            "deployment_time": "12-18 minutes",
            "complexity": "intermediate",
            "pillars": [
                {
                    "title": "Operational Excellence",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "practices": [
                        "Infrastructure as Code with Pulumi for automated, repeatable deployments",
                        "Centralized load balancer management and traffic routing",
                        "Health check monitoring with automatic unhealthy target removal",
                        "Access logs capture all requests for debugging and analytics",
                        "CloudWatch metrics provide real-time ALB performance visibility"
                    ]
                },
                {
                    "title": "Security",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "practices": [
                        "Security group isolation between ALB and backend instances",
                        "HTTPS listener support with ACM certificate integration",
                        "Automatic SSL certificate provisioning for secure communications",
                        "Backend instances only accept traffic from ALB security group",
                        "Multi-tier security architecture (public ALB, private backends)",
                        "VPC endpoints enable private AWS service access without internet exposure"
                    ]
                },
                {
                    "title": "Reliability",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "practices": [
                        "Multi-AZ deployment ensures high availability across availability zones",
                        "Automated health checks remove unhealthy targets from rotation",
                        "Multiple backend instances provide redundancy and failover",
                        "ALB automatically scales to handle traffic spikes",
                        "Cross-zone load balancing distributes traffic evenly"
                    ]
                },
                {
                    "title": "Performance Efficiency",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "practices": [
                        "Elastic Load Balancing distributes traffic efficiently across targets",
                        "Connection multiplexing reduces backend connection overhead",
                        "HTTP/2 and WebSocket support for modern application protocols",
                        "Session stickiness routes repeat requests to same backend",
                        "Target group health checks ensure only healthy instances receive traffic"
                    ]
                },
                {
                    "title": "Cost Optimization",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "practices": [
                        "ALB pricing based on hours used and data processed (~$20-30/month base)",
                        "Shared ALB can serve multiple applications reducing infrastructure duplication",
                        "Health checks prevent wasted requests to unhealthy instances",
                        "Target-based routing enables efficient resource utilization",
                        "VPC endpoints eliminate NAT gateway costs for AWS service access"
                    ]
                },
                {
                    "title": "Sustainability",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "practices": [
                        "AWS-managed service optimized for energy efficiency",
                        "Elastic scaling prevents over-provisioning of infrastructure",
                        "Multi-AZ design maximizes resource utilization across zones",
                        "Health checks reduce wasteful traffic to unhealthy targets",
                        "Efficient traffic distribution minimizes redundant processing"
                    ]
                }
            ]
        }

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        """Get configuration schema from source of truth"""
        return ALBNonProdConfig.get_config_schema()