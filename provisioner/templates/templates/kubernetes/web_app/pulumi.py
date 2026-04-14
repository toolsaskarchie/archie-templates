"""
Kubernetes Simple Web Application Template - Pattern B Implementation

Deploys a simple web application to Kubernetes including Deployment, Service, 
ConfigMap, and optional Ingress. Uses PulumiAtomicFactory for resource creation.
"""

from typing import Any, Dict, Optional
import pulumi
from provisioner.templates.base import template_registry, InfrastructureTemplate
from .config import K8sSimpleWebAppConfig
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory


@template_registry("kubernetes-web-app")
class K8sSimpleWebAppTemplate(InfrastructureTemplate):
    """
    Kubernetes Simple Web Application Template
    
    Creates:
    - Kubernetes Namespace (optional)
    - Kubernetes ConfigMap for environment variables
    - Kubernetes Deployment for containerized application
    - Kubernetes Service for network access
    - Kubernetes Ingress for external access (optional)
    """
    
    def __init__(self, name: str = None, config: Dict[str, Any] = None, **kwargs):
        """Initialize Kubernetes web app template"""
        raw_config = config or kwargs or {}
        if name is None:
            name = raw_config.get('appName', 'k8s-web-app')
        super().__init__(name, raw_config)
        self.config = raw_config
        self.cfg = K8sSimpleWebAppConfig(raw_config)

        self.namespace = None
        self.config_map = None
        self.deployment = None
        self.service = None
        self.ingress = None

    def _cfg(self, key: str, default=None):
        """Read config from root, parameters.kubernetes, or parameters (Rule #6)"""
        params = self.config.get('parameters', {})
        k8s_params = params.get('kubernetes', {}) if isinstance(params, dict) else {}
        return (
            self.config.get(key) or
            (k8s_params.get(key) if isinstance(k8s_params, dict) else None) or
            (params.get(key) if isinstance(params, dict) else None) or
            default
        )

    def create_infrastructure(self) -> Dict[str, Any]:
        """Deploy infrastructure (implements abstract method)"""
        return self.create()

    def create(self) -> Dict[str, Any]:
        """Deploy Kubernetes web app infrastructure"""
        
        # 1. Initialize Kubernetes Provider
        provider = None
        if self.cfg.kubeconfig_content:
            from pulumi_kubernetes import Provider
            provider = Provider(f"{self.name}-provider", kubeconfig=self.cfg.kubeconfig_content)
        
        opts = pulumi.ResourceOptions(provider=provider)
        
        # 2. Namespace
        if self.cfg.namespace != "default":
            self.namespace = factory.create(
                "kubernetes:core/v1:Namespace",
                self.cfg.namespace,
                metadata={"name": self.cfg.namespace},
                opts=opts
            )
            
        # 3. ConfigMap
        config_data = {
            "APP_NAME": self.cfg.app_name,
            "ENVIRONMENT": self.cfg.environment,
        }
        config_data.update(self.cfg.env_vars)

        self.config_map = factory.create(
            "kubernetes:core/v1:ConfigMap",
            f"{self.name}-config",
            metadata={
                "name": f"{self.cfg.app_name}-config",
                "namespace": self.cfg.namespace,
                "labels": self.cfg.resource_labels
            },
            data=config_data,
            opts=opts
        )
        
        # 4. Deployment
        self.deployment = factory.create(
            "kubernetes:apps/v1:Deployment",
            self.name,
            metadata={
                "name": self.cfg.app_name,
                "namespace": self.cfg.namespace,
                "labels": self.cfg.resource_labels
            },
            spec={
                "replicas": self.cfg.replicas,
                "selector": {"match_labels": {"app": self.cfg.app_name}},
                "template": {
                    "metadata": {"labels": {"app": self.cfg.app_name}},
                    "spec": {
                        "containers": [{
                            "name": self.cfg.app_name,
                            "image": self.cfg.image,
                            "ports": [{"container_port": self.cfg.container_port}],
                            "resources": {
                                "limits": {"cpu": self.cfg.cpu_limit, "memory": self.cfg.memory_limit},
                                "requests": {"cpu": self.cfg.cpu_request, "memory": self.cfg.memory_request}
                            },
                            "env_from": [{"config_map_ref": {"name": f"{self.cfg.app_name}-config"}}]
                        }]
                    }
                }
            },
            opts=opts
        )
        
        # 5. Service
        self.service = factory.create(
            "kubernetes:core/v1:Service",
            f"{self.name}-svc",
            metadata={
                "name": f"{self.cfg.app_name}-service",
                "namespace": self.cfg.namespace,
                "labels": self.cfg.resource_labels
            },
            spec={
                "type": self.cfg.service_type,
                "ports": [{"port": self.cfg.service_port, "target_port": self.cfg.container_port, "protocol": "TCP"}],
                "selector": {"app": self.cfg.app_name}
            },
            opts=opts
        )
        
        # 6. Ingress
        if self.cfg.enable_ingress:
            self.ingress = factory.create(
                "kubernetes:networking.k8s.io/v1:Ingress",
                f"{self.name}-ingress",
                metadata={
                    "name": f"{self.cfg.app_name}-ingress",
                    "namespace": self.cfg.namespace,
                    "labels": self.cfg.resource_labels,
                    "annotations": {"kubernetes.io/ingress.class": "nginx"}
                },
                spec={
                    "rules": [{
                        "host": self.cfg.ingress_host,
                        "http": {
                            "paths": [{
                                "path": "/",
                                "path_type": "Prefix",
                                "backend": {
                                    "service": {
                                        "name": f"{self.cfg.app_name}-service",
                                        "port": {"number": self.cfg.service_port}
                                    }
                                }
                            }]
                        }
                    }]
                },
                opts=opts
            )
            
        # Service endpoint
        service_endpoint = self.service.status.apply(
            lambda status: status.load_balancer.ingress[0].ip
            if status and status.load_balancer and status.load_balancer.ingress and len(status.load_balancer.ingress) > 0 and hasattr(status.load_balancer.ingress[0], 'ip')
            else (status.load_balancer.ingress[0].hostname
                  if status and status.load_balancer and status.load_balancer.ingress and len(status.load_balancer.ingress) > 0 and hasattr(status.load_balancer.ingress[0], 'hostname')
                  else "Pending")
        )

        pulumi.export("app_name", self.cfg.app_name)
        pulumi.export("service_type", self.cfg.service_type)
        pulumi.export("service_endpoint", service_endpoint)
            
        return self.get_outputs()

    def get_outputs(self) -> Dict[str, Any]:
        """Get template outputs"""
        if not self.deployment:
            return {}
        return {
            "app_name": self.cfg.app_name,
            "namespace": self.cfg.namespace,
            "service_name": f"{self.cfg.app_name}-service",
            "deployment_name": self.deployment.metadata.apply(lambda m: m.name) if self.deployment else None,
            "service_type": self.cfg.service_type,
        }

    @classmethod
    def get_metadata(cls) -> Dict[str, Any]:
        """Template metadata (Pattern B)"""
        return {
            "name": "kubernetes-web-app",
            "title": "Simple Web App",
            "description": "Deploy a simple web application to Kubernetes with Deployment, Service, and optional Ingress.",
            "category": "compute",
            "cloud": "kubernetes",
            "environment": "nonprod",
            "version": "1.1.0",
            "author": "InnovativeApps",
            "tags": ["kubernetes", "docker", "k8s", "webapp"],
            "base_cost": "$0/month (cluster costs separate)",
            "features": [
                "Kubernetes Deployment with configurable replicas",
                "Service for network access (ClusterIP/NodePort/LoadBalancer)",
                "ConfigMap for environment variable management",
                "Optional Ingress with nginx controller",
                "Namespace isolation for workload separation",
                "Resource limits and requests for right-sizing",
            ],
            "use_cases": [
                "Containerized web application deployment",
                "Microservice hosting on Kubernetes",
                "Development and staging workloads",
                "REST API backends with load balancing",
            ],
            "complexity": "medium",
            "deployment_time": "2-4 minutes",
            "marketplace_group": "COMPUTE",
            "pillars": [
                {
                    "title": "Operational Excellence",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Declarative deployments with configurable replicas and environment variables.",
                    "practices": [
                        "Infrastructure as Code with Pulumi for repeatable Kubernetes deployments",
                        "ConfigMap-driven environment variables for easy configuration updates",
                        "Standardized resource labels for observability and organization",
                        "Optional namespace isolation for workload separation",
                        "Declarative Deployment spec with rolling update strategy"
                    ]
                },
                {
                    "title": "Security",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Namespace isolation with resource limits and network policies.",
                    "practices": [
                        "Namespace isolation separates workloads from other applications",
                        "Resource limits prevent container resource exhaustion attacks",
                        "ConfigMap separates configuration from container images",
                        "Service abstraction hides pod IPs from external access",
                        "Optional Ingress with controlled external routing"
                    ]
                },
                {
                    "title": "Reliability",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Multi-replica deployment with self-healing and load balancing.",
                    "practices": [
                        "Configurable replica count for availability requirements",
                        "Kubernetes self-healing restarts failed containers automatically",
                        "Service load balancing distributes traffic across healthy pods",
                        "Rolling update strategy ensures zero-downtime deployments",
                        "Health checks via Kubernetes liveness and readiness probes"
                    ]
                },
                {
                    "title": "Performance Efficiency",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Right-sized containers with resource requests and limits.",
                    "practices": [
                        "CPU and memory requests ensure guaranteed resources per pod",
                        "Resource limits prevent noisy-neighbor performance degradation",
                        "Configurable container port for application-specific optimization",
                        "Service type selection (ClusterIP, NodePort, LoadBalancer) for access patterns",
                        "Horizontal scaling via replica count adjustment"
                    ]
                },
                {
                    "title": "Cost Optimization",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Minimal resource footprint with right-sized containers.",
                    "practices": [
                        "Resource requests and limits prevent over-provisioning",
                        "Configurable replica count scales to actual demand",
                        "ClusterIP service type avoids load balancer costs when not needed",
                        "Namespace sharing reduces cluster overhead",
                        "Container-based deployment maximizes compute utilization"
                    ]
                },
                {
                    "title": "Sustainability",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Efficient container orchestration with minimal resource waste.",
                    "practices": [
                        "Container bin-packing maximizes node utilization",
                        "Resource requests prevent idle over-provisioning",
                        "Shared cluster infrastructure reduces per-app overhead",
                        "Configurable replicas scale down during low demand"
                    ]
                }
            ]
        }

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        """Get configuration schema"""
        return {
            "type": "object",
            "properties": {
                "appName": {"type": "string", "title": "App Name", "default": "my-web-app"},
                "image": {"type": "string", "title": "Container Image", "default": "nginx:latest"},
                "replicas": {"type": "integer", "title": "Replicas", "default": 2},
                "namespace": {"type": "string", "title": "Namespace", "default": "default"},
                "serviceType": {
                    "type": "string",
                    "title": "Service Type",
                    "enum": ["ClusterIP", "NodePort", "LoadBalancer"],
                    "default": "LoadBalancer"
                },
                "team_name": {
                    "type": "string",
                    "default": "",
                    "title": "Team Name",
                    "description": "Team that owns this resource",
                    "order": 50,
                    "group": "Tags",
                },
            },
            "required": ["appName", "image"]
        }
