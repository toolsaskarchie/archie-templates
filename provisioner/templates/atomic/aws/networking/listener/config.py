"""
Listener Atomic Configuration

Configuration class for standalone AWS Load Balancer Listeners.
"""
from provisioner.templates.base import TemplateConfig


class ListenerAtomicConfig(TemplateConfig):
    """
    Configuration for Listener Atomic Template
    """

    def __init__(self, config_data):
        super().__init__(config_data)

    def get_listener_config(self):
        """Get listener configuration"""
        return {
            "load_balancer_arn": self.get("load_balancer_arn"),
            "port": self.get("port", 80),
            "protocol": self.get("protocol", "HTTP"),
            "target_group_arn": self.get("target_group_arn"),
            "certificate_arn": self.get("certificate_arn"),
            "ssl_policy": self.get("ssl_policy", "ELBSecurityPolicy-2016-08"),
            "project_name": self.get("project_name", "archie"),
            "environment": self.get("environment", "dev")
        }