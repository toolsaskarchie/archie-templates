"""
Kubernetes PersistentVolumeClaim Template

Create a PVC with configurable storage class, size, and access mode.
Provisions persistent storage for stateful workloads.

Base cost: Varies by storage class and size
- PVC with configurable storage class
- Access mode selection (ReadWriteOnce, ReadWriteMany, ReadOnlyMany)
- Storage size configuration
- Optional volume name for static binding
"""

from typing import Any, Dict, Optional
import pulumi
import pulumi_kubernetes as k8s

from provisioner.templates.base import template_registry, InfrastructureTemplate
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory


@template_registry("kubernetes-pvc")
class K8sPVCTemplate(InfrastructureTemplate):
    """
    Kubernetes PersistentVolumeClaim Template

    Creates:
    - Kubernetes Namespace (optional)
    - PersistentVolumeClaim
    """

    def __init__(self, name: str = None, config: Dict[str, Any] = None, **kwargs):
        """Initialize PVC template"""
        raw_config = config or kwargs or {}
        if name is None:
            name = (
                raw_config.get('pvc_name') or
                raw_config.get('project_name') or
                raw_config.get('parameters', {}).get('pvc_name') or
                'pvc'
            )
        super().__init__(name, raw_config)
        self.config = raw_config

        # Resource references
        self.namespace_resource: Optional[object] = None
        self.pvc: Optional[object] = None

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
        """Deploy PVC infrastructure (implements abstract method)"""
        return self.create()

    def create(self) -> Dict[str, Any]:
        """Deploy PersistentVolumeClaim using factory pattern"""

        # Read config
        pvc_name = self._cfg('pvc_name', 'my-pvc')
        namespace = self._cfg('namespace', 'default')
        environment = self._cfg('environment', 'dev')
        project_name = self._cfg('project_name', 'pvc-app')
        team_name = self._cfg('team_name', '')
        storage_size = self._cfg('storage_size', '10Gi')
        storage_class = self._cfg('storage_class', '')
        access_mode = self._cfg('access_mode', 'ReadWriteOnce')
        volume_name = self._cfg('volume_name', '')
        volume_mode = self._cfg('volume_mode', 'Filesystem')

        create_namespace = self._cfg('create_namespace', True)
        if isinstance(create_namespace, str):
            create_namespace = create_namespace.lower() in ('true', '1', 'yes')

        # Standard labels
        labels = {
            "app.kubernetes.io/managed-by": "archie",
            "app.kubernetes.io/name": pvc_name,
            "app.kubernetes.io/component": "storage",
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
                f"{pvc_name}-ns",
                metadata={
                    "name": namespace,
                    "labels": labels,
                },
            )

        # =================================================================
        # LAYER 2: PersistentVolumeClaim
        # =================================================================

        pvc_spec = {
            "access_modes": [access_mode],
            "resources": {
                "requests": {"storage": storage_size},
            },
            "volume_mode": volume_mode,
        }

        if storage_class:
            pvc_spec["storage_class_name"] = storage_class

        if volume_name:
            pvc_spec["volume_name"] = volume_name

        self.pvc = factory.create(
            "kubernetes:core/v1:PersistentVolumeClaim",
            pvc_name,
            metadata={
                "name": pvc_name,
                "namespace": namespace,
                "labels": labels,
                "annotations": {
                    "archie.io/managed": "true",
                },
            },
            spec=pvc_spec,
        )

        # =================================================================
        # Outputs (Rule #2, #7)
        # =================================================================

        pulumi.export('pvc_name', pvc_name)
        pulumi.export('namespace', namespace)
        pulumi.export('storage_size', storage_size)
        pulumi.export('storage_class', storage_class or 'cluster-default')
        pulumi.export('access_mode', access_mode)
        pulumi.export('volume_mode', volume_mode)
        pulumi.export('environment', environment)

        return self.get_outputs()

    def get_outputs(self) -> Dict[str, Any]:
        """Get template outputs"""
        return {
            "pvc_name": self._cfg('pvc_name', 'my-pvc'),
            "namespace": self._cfg('namespace', 'default'),
            "storage_size": self._cfg('storage_size', '10Gi'),
            "access_mode": self._cfg('access_mode', 'ReadWriteOnce'),
            "storage_class": self._cfg('storage_class', '') or 'cluster-default',
        }

    @classmethod
    def get_metadata(cls) -> Dict[str, Any]:
        """Template metadata for catalog UI"""
        return {
            "name": "kubernetes-pvc",
            "title": "PersistentVolumeClaim",
            "description": "Create a Kubernetes PersistentVolumeClaim with configurable storage class, size, access mode, and optional static volume binding.",
            "category": "storage",
            "version": "1.0.0",
            "author": "Archie",
            "cloud": "kubernetes",
            "environment": "nonprod",
            "base_cost": "Varies",
            "features": [
                "Configurable storage size",
                "Storage class selection for SSD, HDD, or cloud-specific classes",
                "Access mode: ReadWriteOnce, ReadWriteMany, ReadOnlyMany",
                "Optional static volume binding",
                "Filesystem or Block volume mode",
                "Optional namespace creation",
            ],
            "tags": ["kubernetes", "pvc", "storage", "persistent", "volume"],
            "deployment_time": "1 minute",
            "complexity": "beginner",
            "use_cases": [
                "Database data volumes",
                "Application file uploads and media storage",
                "Shared storage for multi-pod workloads",
                "Log and audit data persistence",
                "ML model and dataset storage",
            ],
            "pillars": [
                {
                    "title": "Operational Excellence",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Declarative storage provisioning with clear lifecycle management",
                    "practices": [
                        "Infrastructure as Code for repeatable storage provisioning",
                        "Labels enable storage inventory and lifecycle tracking",
                        "Storage class abstraction decouples from provider specifics",
                        "Annotations provide metadata for tooling integration",
                        "Namespace-scoped for organizational clarity",
                    ]
                },
                {
                    "title": "Security",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Access mode controls and namespace isolation for storage",
                    "practices": [
                        "ReadWriteOnce restricts to single-node access",
                        "Namespace isolation limits storage visibility",
                        "Storage class can enforce encryption at rest",
                        "Labels enable RBAC targeting for storage access",
                        "Managed annotations provide audit trail",
                    ]
                },
                {
                    "title": "Reliability",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Persistent storage survives pod restarts, rescheduling, and upgrades",
                    "practices": [
                        "Data persists across pod lifecycle events",
                        "PVC binding ensures storage is ready before pod starts",
                        "Cloud-backed storage classes provide replication",
                        "Static binding option for pre-provisioned volumes",
                        "Reclaim policy controls data retention on PVC delete",
                    ]
                },
                {
                    "title": "Performance Efficiency",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Storage class selection enables SSD or throughput-optimized storage",
                    "practices": [
                        "Storage class selection matches IO requirements",
                        "Block mode available for raw device access",
                        "Right-sized storage prevents over-provisioning",
                        "ReadWriteMany enables multi-pod concurrent access",
                    ]
                },
                {
                    "title": "Cost Optimization",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Right-sized storage with appropriate class selection",
                    "practices": [
                        "Storage sized to actual needs prevents waste",
                        "Storage class selection matches cost to performance needs",
                        "HDD classes available for cost-sensitive workloads",
                        "Namespace quota integration prevents runaway storage costs",
                    ]
                },
                {
                    "title": "Sustainability",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Right-sized storage minimizes unnecessary disk allocation",
                    "practices": [
                        "Sized-to-need storage reduces wasted disk space",
                        "Cloud provider dynamic provisioning avoids pre-allocated waste",
                        "Appropriate access modes prevent redundant copies",
                        "Labels support lifecycle-based storage cleanup",
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
                    "default": "pvc-app",
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
                "pvc_name": {
                    "type": "string",
                    "default": "my-pvc",
                    "title": "PVC Name",
                    "description": "PersistentVolumeClaim resource name",
                    "order": 3,
                    "group": "Essentials",
                    "isEssential": True,
                },
                "storage_size": {
                    "type": "string",
                    "default": "10Gi",
                    "title": "Storage Size",
                    "description": "Requested storage capacity (e.g., 1Gi, 10Gi, 100Gi)",
                    "order": 10,
                    "group": "Storage",
                    "cost_impact": "Varies by size and class",
                },
                "storage_class": {
                    "type": "string",
                    "default": "",
                    "title": "Storage Class",
                    "description": "Kubernetes storage class (leave empty for cluster default). Examples: gp3, standard, premium-rwo",
                    "order": 11,
                    "group": "Storage",
                },
                "access_mode": {
                    "type": "string",
                    "default": "ReadWriteOnce",
                    "title": "Access Mode",
                    "description": "How the volume can be mounted",
                    "enum": ["ReadWriteOnce", "ReadWriteMany", "ReadOnlyMany"],
                    "order": 12,
                    "group": "Storage",
                },
                "volume_mode": {
                    "type": "string",
                    "default": "Filesystem",
                    "title": "Volume Mode",
                    "description": "Filesystem for mounted directory, Block for raw device access",
                    "enum": ["Filesystem", "Block"],
                    "order": 13,
                    "group": "Storage",
                },
                "volume_name": {
                    "type": "string",
                    "default": "",
                    "title": "Volume Name (Static Binding)",
                    "description": "Bind to a specific PersistentVolume by name (leave empty for dynamic provisioning)",
                    "order": 14,
                    "group": "Storage",
                },
                "namespace": {
                    "type": "string",
                    "default": "default",
                    "title": "Namespace",
                    "description": "Kubernetes namespace for the PVC",
                    "order": 20,
                    "group": "Deployment",
                },
                "team_name": {
                    "type": "string",
                    "default": "",
                    "title": "Team Name",
                    "description": "Team that owns this storage volume",
                    "order": 50,
                    "group": "Tags",
                },
            },
            "required": ["pvc_name", "storage_size"],
        }
