"""
Target Group Atomic Configuration

Configuration class for standalone AWS Load Balancer Target Groups.
"""
from provisioner.templates.base import TemplateConfig


class TargetGroupAtomicConfig(TemplateConfig):
    """
    Configuration for Target Group Atomic Template
    """

    def __init__(self, config_data):
        super().__init__(config_data)

    def get_target_group_config(self):
        """Get target group configuration"""
        return {
            "target_group_name": self.get("target_group_name", f"{self.get('project_name', 'archie')}-tg"),
            "port": self.get("port", 80),
            "protocol": self.get("protocol", "HTTP"),
            "vpc_id": self.get("vpc_id"),
            "target_type": self.get("target_type", "instance"),
            "health_check": self.get_health_check_config(),
            "project_name": self.get("project_name", "archie"),
            "environment": self.get("environment", "dev")
        }

    def get_health_check_config(self):
        """Get health check configuration"""
        return {
            "enabled": self.get("health_check_enabled", True),
            "healthy_threshold": self.get("healthy_threshold", 2),
            "unhealthy_threshold": self.get("unhealthy_threshold", 2),
            "timeout": self.get("health_check_timeout", 5),
            "interval": self.get("health_check_interval", 30),
            "matcher": self.get("health_check_matcher", "200"),
            "path": self.get("health_check_path", "/"),
            "port": self.get("health_check_port", "traffic-port"),
            "protocol": self.get("health_check_protocol", "HTTP")
        }