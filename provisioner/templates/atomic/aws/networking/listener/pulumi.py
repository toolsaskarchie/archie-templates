"""
Listener Template

Atomic template for deploying standalone AWS Load Balancer Listeners.
Perfect for advanced users building custom load balancer architectures.
"""
from provisioner.templates.base import InfrastructureTemplate, template_registry
from typing import Any, Dict
import pulumi_aws as aws
import pulumi


@template_registry("aws-listener-atomic")
class ListenerAtomicTemplate(InfrastructureTemplate):
    """
    Listener Template

    Deploys a standalone AWS Load Balancer Listener.
    Requires an existing Load Balancer ARN and Target Group ARN.
    """

    def __init__(self, name, config):
        super().__init__(name, config)
        self.template_name = "listener-atomic"

    def create_infrastructure(self):
        """Create the listener infrastructure"""
        # Get configuration
        load_balancer_arn = self.config.get("load_balancer_arn")
        port = self.config.get("port", 80)
        protocol = self.config.get("protocol", "HTTP")
        target_group_arn = self.config.get("target_group_arn")

        if not load_balancer_arn:
            raise ValueError("load_balancer_arn is required for listener deployment")
        if not target_group_arn:
            raise ValueError("target_group_arn is required for listener deployment")

        # Prepare default actions
        default_actions = [{
            "type": "forward",
            "target_group_arn": target_group_arn
        }]

        # Create listener component
        # Only set SSL policy for HTTPS listeners
        listener_args = {
            "load_balancer_arn": load_balancer_arn,
            "port": port,
            "protocol": protocol,
            "default_actions": default_actions,
            "tags": {
                "Name": f"{self.name}-listener",
                "Project": self.config.get("project_name", "archie"),
                "Environment": self.config.get("environment", "dev"),
                "ManagedBy": "Archie"
            }
        }
        
        # Only add SSL-related parameters for HTTPS listeners
        if protocol == "HTTPS":
            listener_args["certificate_arn"] = self.config.get("certificate_arn")
            listener_args["ssl_policy"] = self.config.get("ssl_policy", "ELBSecurityPolicy-2016-08")
        
        self.listener = aws.lb.Listener(
            f"{self.name}-listener",
            **listener_args
        )

        # Export outputs
        self.outputs = {
            "listener_arn": self.listener.arn,
            "listener_id": self.listener.id,
        }

        return self.outputs

    def get_outputs(self) -> Dict[str, Any]:
        """Get template outputs"""
        if not hasattr(self, 'listener') or not self.listener:
            return {}
        return {
            "listener_arn": self.listener.arn,
            "listener_id": self.listener.id,
        }

    @classmethod
    def get_metadata(cls) -> Dict[str, Any]:
        """Template metadata"""
        return {
            "name": "listener-atomic",
            "title": "Load Balancer Listener",
            "subtitle": "Single listener resource",
            "description": "Create a standalone load balancer listener. Requires existing load balancer and target group.",
            "category": "networking",
            "provider": "aws",
            "tier": "atomic",
            "complexity": "simple",
            "icon": "🎧",
            "version": "1.0.0",
            "status": "stable",
            "estimated_cost": "$0/month",
            "deployment_time": "1 minute",
            "use_cases": [
                "Add listener to existing load balancer",
                "Expert users building custom architectures"
            ],
            "features": [
                "HTTP/HTTPS listener",
                "SSL/TLS support",
                "Custom SSL policies",
                "Forward to target group"
            ],
            "outputs": [
                "Listener ARN",
                "Listener ID"
            ],
            "prerequisites": [
                "Load balancer must exist",
                "Target group must exist"
            ],
            "tags": [
                "listener",
                "load-balancer",
                "networking",
                "atomic"
            ]
        }
