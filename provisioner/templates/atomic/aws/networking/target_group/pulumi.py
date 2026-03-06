"""
Target Group Template

Atomic template for deploying standalone AWS Load Balancer Target Groups.
Perfect for advanced users building custom load balancer architectures.
"""
from provisioner.templates.base import InfrastructureTemplate, template_registry
from typing import Any, Dict
import pulumi_aws as aws
import pulumi


@template_registry("aws-target-group-atomic")
class TargetGroupAtomicTemplate(InfrastructureTemplate):
    """
    Target Group Template

    Deploys a standalone AWS Load Balancer Target Group.
    Requires an existing VPC ID.
    """

    def __init__(self, name, config):
        super().__init__(name, config)
        self.template_name = "target-group-atomic"

    def create_infrastructure(self):
        """Create the target group infrastructure"""
        # Get configuration
        target_group_name = self.config.get("target_group_name", f"{self.name}-tg")
        # AWS target group name max length is 32 characters
        if len(target_group_name) > 32:
            target_group_name = target_group_name[:32].rstrip('-')
        port = self.config.get("port", 80)
        protocol = self.config.get("protocol", "HTTP")
        vpc_id = self.config.get("vpc_id")
        target_type = self.config.get("target_type", "instance")

        if not vpc_id:
            raise ValueError("vpc_id is required for target group deployment")

        # Create target group component
        self.target_group = aws.lb.TargetGroup(
            f"{self.name}-target-group",
            name=target_group_name,
            port=port,
            protocol=protocol,
            vpc_id=vpc_id,
            target_type=target_type,
            health_check=self.config.get("health_check", {}),
            tags={
                "Name": target_group_name,
                "Project": self.config.get("project_name", "archie"),
                "Environment": self.config.get("environment", "dev"),
                "ManagedBy": "Archie"
            }
        )

        # Export outputs
        self.outputs = {
            "target_group_arn": self.target_group.arn,
            "target_group_name": self.target_group.name,
            "target_group_id": self.target_group.id,
        }

        return self.outputs

    def get_outputs(self) -> Dict[str, Any]:
        """Get template outputs"""
        if not hasattr(self, 'target_group') or not self.target_group:
            return {}
        return {
            "target_group_arn": self.target_group.arn,
            "target_group_name": self.target_group.name,
            "target_group_id": self.target_group.id,
        }

    @classmethod
    def get_metadata(cls) -> Dict[str, Any]:
        """Template metadata"""
        return {
            "name": "target-group-atomic",
            "title": "Target Group",
            "subtitle": "Single target group resource",
            "description": "Create a standalone load balancer target group. Requires existing VPC.",
            "category": "networking",
            "provider": "aws",
            "tier": "atomic",
            "complexity": "simple",
            "icon": "🎯",
            "version": "1.0.0",
            "status": "stable",
            "estimated_cost": "$0/month",
            "deployment_time": "1 minute",
            "use_cases": [
                "Add target group to existing infrastructure",
                "Expert users building custom architectures"
            ],
            "features": [
                "HTTP/HTTPS target group",
                "Health check configuration",
                "Instance or IP target types",
                "Custom port and protocol"
            ],
            "outputs": [
                "Target group ARN",
                "Target group name",
                "Target group ID"
            ],
            "prerequisites": [
                "VPC must exist"
            ],
            "tags": [
                "target-group",
                "load-balancer",
                "networking",
                "atomic"
            ]
        }
