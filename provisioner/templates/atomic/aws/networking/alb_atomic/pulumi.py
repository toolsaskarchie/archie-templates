"""
ALB Template

Atomic template for deploying standalone AWS Application Load Balancers.
Perfect for advanced users building custom load balancer architectures.
"""
from provisioner.templates.base import InfrastructureTemplate, template_registry
from typing import Any, Dict, List, Optional
import pulumi
import pulumi_aws as aws


@template_registry("aws-alb-atomic")
class ALBAtomicTemplate(InfrastructureTemplate):
    """
    Application Load Balancer Template

    Deploys a standalone AWS Application Load Balancer directly (no ComponentResource wrapper).
    Requires subnet IDs and security group IDs.
    """

    def __init__(self, name: str, config: Dict[str, Any], **kwargs):
        super().__init__(name, config, **kwargs)
        self.template_name = "alb-atomic"
        self.alb: Optional[aws.lb.LoadBalancer] = None

    def create_infrastructure(self) -> Dict[str, Any]:
        """Create the ALB infrastructure directly - shows as actual AWS resource in preview"""
        # Get configuration
        alb_name = self.config.get("alb_name", f"{self.name}")
        subnets = self.config.get("subnets", [])
        security_groups = self.config.get("security_groups", [])
        internal = self.config.get("internal", False)
        enable_deletion_protection = self.config.get("enable_deletion_protection", False)
        enable_http2 = self.config.get("enable_http2", True)
        enable_cross_zone_load_balancing = self.config.get("enable_cross_zone_load_balancing", True)
        idle_timeout = self.config.get("idle_timeout", 60)
        
        if not subnets or len(subnets) < 2:
            raise ValueError("At least 2 subnet IDs are required for ALB deployment")
        if not security_groups:
            raise ValueError("At least 1 security group ID is required for ALB deployment")

        tags = {
            "Name": alb_name,
            "Project": self.config.get("project_name", "archie"),
            "Environment": self.config.get("environment", "dev"),
            "ManagedBy": "Archie"
        }

        # Create ALB directly (no ComponentResource wrapper)
        self.alb = aws.lb.LoadBalancer(
            f"{self.name}-alb",
            name=alb_name,
            load_balancer_type="application",
            subnets=subnets,
            security_groups=security_groups,
            internal=internal,
            enable_deletion_protection=enable_deletion_protection,
            enable_http2=enable_http2,
            enable_cross_zone_load_balancing=enable_cross_zone_load_balancing,
            idle_timeout=idle_timeout,
            tags=tags
        )

        return {
            "alb_id": self.alb.id,
            "alb_arn": self.alb.arn,
            "alb_dns_name": self.alb.dns_name,
            "alb_zone_id": self.alb.zone_id,
            "alb_name": self.alb.name
        }

    def get_outputs(self) -> Dict[str, Any]:
        """Return the outputs of the infrastructure"""
        if not self.alb:
            raise RuntimeError("Infrastructure not created yet. Call create_infrastructure() first.")
        
        return {
            "alb_id": self.alb.id,
            "alb_arn": self.alb.arn,
            "alb_dns_name": self.alb.dns_name,
            "alb_zone_id": self.alb.zone_id,
            "alb_name": self.alb.name
        }

    @classmethod
    def get_metadata(cls) -> Dict[str, Any]:
        """Template metadata"""
        return {
            "name": "alb-atomic",
            "title": "Application Load Balancer",
            "subtitle": "Single ALB resource",
            "description": "Create a standalone Application Load Balancer. Requires existing VPC, subnets, and security groups.",
            "category": "networking",
            "provider": "aws",
            "tier": "atomic",
            "complexity": "simple",
            "icon": "⚖️",
            "version": "1.0.0",
            "status": "stable",
            "estimated_cost": "$16-30/month",
            "deployment_time": "2-3 minutes",
            "use_cases": [
                "Add load balancer to existing infrastructure",
                "Expert users building custom architectures"
            ],
            "features": [
                "Application Load Balancer",
                "HTTP/HTTPS support",
                "Cross-zone load balancing",
                "Configurable idle timeout"
            ],
            "outputs": [
                "ALB ID",
                "ALB ARN",
                "ALB DNS name",
                "ALB hosted zone ID"
            ],
            "prerequisites": [
                "VPC must exist",
                "At least 2 subnets in different AZs",
                "Security groups must exist"
            ],
            "tags": [
                "alb",
                "load-balancer",
                "networking",
                "atomic"
            ]
        }
