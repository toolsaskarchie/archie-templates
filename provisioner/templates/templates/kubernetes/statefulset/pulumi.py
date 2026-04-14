"""
Kubernetes StatefulSet Template

Deploy a StatefulSet with PersistentVolumeClaim templates and a headless Service.
Ideal for stateful workloads like databases, caches, and message queues.

Base cost: $0/month (compute and storage costs depend on cluster)
- StatefulSet with ordered pod management
- Headless Service for stable network identity
- PVC template for per-pod persistent storage
- Configurable resource limits and requests
"""

from typing import Any, Dict, Optional
import pulumi
import pulumi_kubernetes as k8s

from provisioner.templates.base import template_registry, InfrastructureTemplate
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory


@template_registry("kubernetes-statefulset")
class K8sStatefulSetTemplate(InfrastructureTemplate):
    """
    Kubernetes StatefulSet Template

    Creates:
    - Kubernetes Namespace (optional)
    - Headless Service for stable DNS
    - StatefulSet with PVC templates
    """

    def __init__(self, name: str = None, config: Dict[str, Any] = None, **kwargs):
        """Initialize StatefulSet template"""
        raw_config = config or kwargs or {}
        if name is None:
            name = (
                raw_config.get('app_name') or
                raw_config.get('project_name') or
                raw_config.get('parameters', {}).get('app_name') or
                'statefulset'
            )
        super().__init__(name, raw_config)
        self.config = raw_config

        # Resource references
        self.namespace_resource: Optional[object] = None
        self.headless_service: Optional[object] = None
        self.statefulset: Optional[object] = None

    def _cfg(self, key: str, default=None):
        """Read config from root, parameters, or parameters.kubernetes (Rule #6)"""
        params = self.config.get('parameters', {})
        k8s_params = params.get('kubernetes', {}) if isinstance(params, dict) else {}
        return (
            self.config.get(key) or
            (k8s_params.get(key) if isinstance(k8s_params, dict) else None) or
            (params.get(key) if isinstance(params, dict) else None) or
            default
        )

    def create_infrastructure(self) -> Dict[str, Any]:
        """Deploy StatefulSet infrastructure (implements abstract method)"""
        return self.create()

    def create(self) -> Dict[str, Any]:
        """Deploy StatefulSet with headless Service and PVC templates"""

        # Read config
        app_name = self._cfg('app_name', 'my-statefulset')
        namespace = self._cfg('namespace', 'default')
        environment = self._cfg('environment', 'dev')
        project_name = self._cfg('project_name', 'statefulset-app')
        team_name = self._cfg('team_name', '')
        image = self._cfg('image', 'postgres:15')
        replicas = int(self._cfg('replicas', 3))
        container_port = int(self._cfg('container_port', 5432))
        cpu_request = self._cfg('cpu_request', '250m')
        cpu_limit = self._cfg('cpu_limit', '500m')
        memory_request = self._cfg('memory_request', '256Mi')
        memory_limit = self._cfg('memory_limit', '512Mi')
        storage_size = self._cfg('storage_size', '10Gi')
        storage_class = self._cfg('storage_class', '')
        mount_path = self._cfg('mount_path', '/var/lib/data')
        service_port = int(self._cfg('service_port', 5432))
        pod_management_policy = self._cfg('pod_management_policy', 'OrderedReady')

        create_namespace = self._cfg('create_namespace', True)
        if isinstance(create_namespace, str):
            create_namespace = create_namespace.lower() in ('true', '1', 'yes')

        # Standard labels
        labels = {
            "app.kubernetes.io/managed-by": "archie",
            "app.kubernetes.io/name": app_name,
            "app.kubernetes.io/component": "statefulset",
            "archie/environment": environment,
            "archie/project": project_name,
        }
        if team_name:
            labels["archie/team"] = team_name

        # =================================================================
        # LAYER 1: Namespace (optional)
        # =================================================================

        if namespace != "default" and create_namespace:
            self.namespace_resource = factory.create(
                "kubernetes:core/v1:Namespace",
                f"{app_name}-ns",
                metadata={
                    "name": namespace,
                    "labels": labels,
                },
            )

        # =================================================================
        # LAYER 2: Headless Service
        # =================================================================

        self.headless_service = factory.create(
            "kubernetes:core/v1:Service",
            f"{app_name}-headless",
            metadata={
                "name": f"{app_name}-headless",
                "namespace": namespace,
                "labels": labels,
            },
            spec={
                "cluster_ip": "None",
                "ports": [{
                    "port": service_port,
                    "target_port": container_port,
                    "protocol": "TCP",
                    "name": "primary",
                }],
                "selector": {"app.kubernetes.io/name": app_name},
            },
        )

        # =================================================================
        # LAYER 3: StatefulSet
        # =================================================================

        volume_claim_templates = [{
            "metadata": {
                "name": "data",
                "labels": labels,
            },
            "spec": {
                "access_modes": ["ReadWriteOnce"],
                "resources": {
                    "requests": {"storage": storage_size},
                },
            },
        }]

        # Add storage class if specified
        if storage_class:
            volume_claim_templates[0]["spec"]["storage_class_name"] = storage_class

        self.statefulset = factory.create(
            "kubernetes:apps/v1:StatefulSet",
            app_name,
            metadata={
                "name": app_name,
                "namespace": namespace,
                "labels": labels,
            },
            spec={
                "service_name": f"{app_name}-headless",
                "replicas": replicas,
                "pod_management_policy": pod_management_policy,
                "selector": {"match_labels": {"app.kubernetes.io/name": app_name}},
                "template": {
                    "metadata": {
                        "labels": {
                            **labels,
                            "app.kubernetes.io/name": app_name,
                        },
                    },
                    "spec": {
                        "containers": [{
                            "name": app_name,
                            "image": image,
                            "ports": [{"container_port": container_port, "name": "primary"}],
                            "resources": {
                                "limits": {"cpu": cpu_limit, "memory": memory_limit},
                                "requests": {"cpu": cpu_request, "memory": memory_request},
                            },
                            "volume_mounts": [{
                                "name": "data",
                                "mount_path": mount_path,
                            }],
                        }],
                    },
                },
                "volume_claim_templates": volume_claim_templates,
            },
        )

        # =================================================================
        # Outputs (Rule #2, #7)
        # =================================================================

        pulumi.export('app_name', app_name)
        pulumi.export('namespace', namespace)
        pulumi.export('headless_service_name', f"{app_name}-headless")
        pulumi.export('replicas', replicas)
        pulumi.export('storage_size', storage_size)
        pulumi.export('environment', environment)
        pulumi.export('container_port', container_port)
        pulumi.export('dns_pattern', f"{app_name}-{{0..{replicas - 1}}}.{app_name}-headless.{namespace}.svc.cluster.local")

        return self.get_outputs()

    def get_outputs(self) -> Dict[str, Any]:
        """Get template outputs"""
        app_name = self._cfg('app_name', 'my-statefulset')
        namespace = self._cfg('namespace', 'default')
        replicas = int(self._cfg('replicas', 3))
        return {
            "app_name": app_name,
            "namespace": namespace,
            "headless_service_name": f"{app_name}-headless",
            "replicas": replicas,
            "statefulset_name": app_name,
            "dns_pattern": f"{app_name}-{{0..{replicas - 1}}}.{app_name}-headless.{namespace}.svc.cluster.local",
        }

    @classmethod
    def get_metadata(cls) -> Dict[str, Any]:
        """Template metadata for catalog UI"""
        return {
            "name": "kubernetes-statefulset",
            "title": "StatefulSet with Persistent Storage",
            "description": "Deploy a Kubernetes StatefulSet with PVC templates and headless Service for stateful workloads like databases and caches.",
            "category": "compute",
            "version": "1.0.0",
            "author": "Archie",
            "cloud": "kubernetes",
            "environment": "nonprod",
            "base_cost": "$0/month",
            "features": [
                "StatefulSet with ordered pod management",
                "Headless Service for stable DNS per pod",
                "PersistentVolumeClaim template per replica",
                "Configurable storage class and size",
                "Resource limits and requests",
                "Stable network identity (pod-0, pod-1, etc.)",
            ],
            "tags": ["kubernetes", "statefulset", "persistent", "database", "stateful"],
            "deployment_time": "2-5 minutes",
            "complexity": "intermediate",
            "use_cases": [
                "PostgreSQL / MySQL replicated clusters",
                "Redis Sentinel or Redis Cluster",
                "Elasticsearch or OpenSearch nodes",
                "Kafka brokers with persistent topics",
                "ZooKeeper ensembles",
            ],
            "pillars": [
                {
                    "title": "Operational Excellence",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Ordered pod management with stable identity for predictable operations",
                    "practices": [
                        "Ordered pod startup and shutdown for safe cluster formation",
                        "Stable DNS names per pod for service discovery",
                        "PVC per pod ensures data survives pod restarts",
                        "Infrastructure as Code with Pulumi for repeatable deployments",
                        "Configurable pod management policy (OrderedReady/Parallel)",
                    ]
                },
                {
                    "title": "Security",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Namespace isolation with resource limits preventing resource exhaustion",
                    "practices": [
                        "Namespace isolation separates workloads",
                        "Resource limits prevent container resource exhaustion",
                        "Headless service limits network exposure to cluster-internal",
                        "PVC access mode restricts storage to single pod",
                        "Labels enable RBAC and network policy targeting",
                    ]
                },
                {
                    "title": "Reliability",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Persistent storage with ordered lifecycle ensures data durability",
                    "practices": [
                        "PersistentVolumeClaims survive pod restarts and rescheduling",
                        "Ordered startup ensures leader election and quorum formation",
                        "Stable network identity enables reliable peer discovery",
                        "Kubernetes self-healing restarts failed pods automatically",
                        "Volume data retained even after StatefulSet deletion",
                    ]
                },
                {
                    "title": "Performance Efficiency",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Right-sized containers with dedicated persistent storage per pod",
                    "practices": [
                        "CPU and memory requests ensure guaranteed resources",
                        "Per-pod storage eliminates shared disk bottlenecks",
                        "Configurable storage class for SSD or HDD selection",
                        "Horizontal scaling via replica count adjustment",
                    ]
                },
                {
                    "title": "Cost Optimization",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Right-sized storage with configurable replica count",
                    "practices": [
                        "Storage sized per workload prevents over-provisioning",
                        "Configurable replica count matches actual demand",
                        "Headless service avoids load balancer costs",
                        "Resource requests enable efficient bin-packing",
                    ]
                },
                {
                    "title": "Sustainability",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Efficient resource utilization with right-sized storage and compute",
                    "practices": [
                        "Per-pod storage avoids over-provisioned shared volumes",
                        "Resource requests prevent idle over-provisioning",
                        "Container bin-packing maximizes node utilization",
                        "Scale-to-zero possible by setting replicas to 0",
                    ]
                },
            ],
        }

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        """Configuration schema for deploy form"""
        return {
            "type": "object",
            "properties": {
                "project_name": {
                    "type": "string",
                    "default": "statefulset-app",
                    "title": "Project Name",
                    "description": "Project identifier used in resource labels",
                    "order": 1,
                    "group": "Essentials",
                    "isEssential": True,
                },
                "environment": {
                    "type": "string",
                    "default": "dev",
                    "title": "Environment",
                    "description": "Deployment environment",
                    "enum": ["dev", "staging", "prod"],
                    "order": 2,
                    "group": "Essentials",
                    "isEssential": True,
                },
                "app_name": {
                    "type": "string",
                    "default": "my-statefulset",
                    "title": "App Name",
                    "description": "StatefulSet and headless service name",
                    "order": 3,
                    "group": "Essentials",
                    "isEssential": True,
                },
                "image": {
                    "type": "string",
                    "default": "postgres:15",
                    "title": "Container Image",
                    "description": "Docker image for the StatefulSet pods",
                    "order": 10,
                    "group": "Container",
                },
                "replicas": {
                    "type": "number",
                    "default": 3,
                    "title": "Replicas",
                    "description": "Number of StatefulSet pods",
                    "minimum": 1,
                    "maximum": 20,
                    "order": 11,
                    "group": "Container",
                },
                "container_port": {
                    "type": "number",
                    "default": 5432,
                    "title": "Container Port",
                    "description": "Primary port exposed by the container",
                    "order": 12,
                    "group": "Container",
                },
                "cpu_request": {
                    "type": "string",
                    "default": "250m",
                    "title": "CPU Request",
                    "description": "Guaranteed CPU per pod (e.g., 250m, 1)",
                    "order": 13,
                    "group": "Container",
                },
                "cpu_limit": {
                    "type": "string",
                    "default": "500m",
                    "title": "CPU Limit",
                    "description": "Maximum CPU per pod",
                    "order": 14,
                    "group": "Container",
                },
                "memory_request": {
                    "type": "string",
                    "default": "256Mi",
                    "title": "Memory Request",
                    "description": "Guaranteed memory per pod (e.g., 256Mi, 1Gi)",
                    "order": 15,
                    "group": "Container",
                },
                "memory_limit": {
                    "type": "string",
                    "default": "512Mi",
                    "title": "Memory Limit",
                    "description": "Maximum memory per pod",
                    "order": 16,
                    "group": "Container",
                },
                "storage_size": {
                    "type": "string",
                    "default": "10Gi",
                    "title": "Storage Size",
                    "description": "Persistent volume size per pod (e.g., 10Gi, 50Gi)",
                    "order": 20,
                    "group": "Storage",
                    "cost_impact": "Varies by storage class",
                },
                "storage_class": {
                    "type": "string",
                    "default": "",
                    "title": "Storage Class",
                    "description": "Kubernetes storage class (leave empty for cluster default)",
                    "order": 21,
                    "group": "Storage",
                },
                "mount_path": {
                    "type": "string",
                    "default": "/var/lib/data",
                    "title": "Mount Path",
                    "description": "Container path to mount persistent volume",
                    "order": 22,
                    "group": "Storage",
                },
                "namespace": {
                    "type": "string",
                    "default": "default",
                    "title": "Namespace",
                    "description": "Kubernetes namespace for the StatefulSet",
                    "order": 30,
                    "group": "Deployment",
                },
                "pod_management_policy": {
                    "type": "string",
                    "default": "OrderedReady",
                    "title": "Pod Management Policy",
                    "description": "OrderedReady for sequential, Parallel for simultaneous startup",
                    "enum": ["OrderedReady", "Parallel"],
                    "order": 31,
                    "group": "Deployment",
                },
                "team_name": {
                    "type": "string",
                    "default": "",
                    "title": "Team Name",
                    "description": "Team that owns this workload",
                    "order": 50,
                    "group": "Tags",
                },
            },
            "required": ["app_name", "image"],
        }
