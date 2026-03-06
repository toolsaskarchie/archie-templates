"""Configuration for Kubernetes Simple Web Application template."""
from typing import Optional, Dict, Any


class K8sSimpleWebAppConfig:
    """Configuration for Kubernetes Simple Web Application template.

    Handles configuration for deploying a simple web application to Kubernetes
    including Deployment, Service, Ingress, and ConfigMap resources.
    """

    def __init__(self, raw_config: Dict[str, Any]):
        self.raw_config = raw_config
        self.parameters = self.raw_config.get('parameters', {}).get('kubernetes', {})

        # Core attributes
        self.environment = self.raw_config.get('environment', 'nonprod')

        # Kubernetes-specific configuration
        self.namespace = self.get_parameter('namespace', 'default')
        self.app_name = self.get_parameter('appName', 'simple-web-app')

        # Container configuration
        self.image = self.get_parameter('image', 'nginx:latest')
        self.replicas = int(self.get_parameter('replicas', 2))
        self.container_port = int(self.get_parameter('containerPort', 80))

        # Service configuration
        self.service_type = self.get_parameter('serviceType', 'LoadBalancer')
        self.service_port = int(self.get_parameter('servicePort', 80))

        # Ingress configuration
        self.enable_ingress = self.get_parameter('enableIngress', False)
        self.ingress_host = self.get_parameter('ingressHost', None)

        # Resource limits
        self.cpu_limit = self.get_parameter('cpuLimit', '500m')
        self.memory_limit = self.get_parameter('memoryLimit', '512Mi')
        self.cpu_request = self.get_parameter('cpuRequest', '250m')
        self.memory_request = self.get_parameter('memoryRequest', '256Mi')

        # Environment variables for the container
        self.env_vars = self.get_parameter('envVars', {})

        # Labels
        self.labels = self.raw_config.get('labels', {})

        # Kubeconfig file content (uploaded by user)
        self.kubeconfig_content = self.raw_config.get('kubeconfig', '')

        # Validate
        self._validate()

    def _validate(self):
        """Validate configuration"""
        if not self.app_name:
            raise ValueError("appName is required")

        if not self.image:
            raise ValueError("image is required")

        if self.replicas < 1:
            raise ValueError("replicas must be at least 1")

        if self.service_type not in ['ClusterIP', 'NodePort', 'LoadBalancer']:
            raise ValueError(f"serviceType must be ClusterIP, NodePort, or LoadBalancer, got: {self.service_type}")

        if self.enable_ingress and not self.ingress_host:
            raise ValueError("ingressHost is required when enableIngress is true")

        if not self.kubeconfig_content:
            raise ValueError("kubeconfig file is required for Kubernetes deployments")

    def get_parameter(self, key: str, default: Any = None) -> Any:
        """Get a parameter from the configuration."""
        return self.parameters.get(key, default)

    @property
    def resource_labels(self) -> Dict[str, str]:
        """Get resource labels for Kubernetes resources."""
        base_labels = {
            "app": self.app_name,
            "environment": self.environment,
            "managed-by": "archie"
        }
        base_labels.update(self.labels)
        return base_labels
