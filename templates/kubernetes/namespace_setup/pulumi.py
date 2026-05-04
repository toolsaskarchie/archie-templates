"""
Kubernetes Namespace Setup Template

Create a fully governed namespace with ResourceQuota, LimitRange, and default
deny NetworkPolicy. Provides a secure, resource-bounded environment for teams.

Base cost: $0/month (namespace governance is free)
- Namespace with labels and annotations
- ResourceQuota for CPU, memory, and pod count limits
- LimitRange for default container resource limits
- Default-deny NetworkPolicy for network isolation
"""

from typing import Any, Dict, Optional
import pulumi
import pulumi_kubernetes as k8s

from provisioner.templates.base import template_registry, InfrastructureTemplate
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory


@template_registry("kubernetes-namespace-setup")
class K8sNamespaceSetupTemplate(InfrastructureTemplate):
    """
    Kubernetes Namespace Setup Template

    Creates:
    - Namespace with governance labels
    - ResourceQuota (CPU, memory, pod limits)
    - LimitRange (default container resources)
    - NetworkPolicy (default deny ingress)
    """

    def __init__(self, name: str = None, config: Dict[str, Any] = None, **kwargs):
        """Initialize Namespace Setup template"""
        raw_config = config or kwargs or {}
        if name is None:
            name = (
                raw_config.get('namespace_name') or
                raw_config.get('project_name') or
                raw_config.get('parameters', {}).get('namespace_name') or
                'namespace-setup'
            )
        super().__init__(name, raw_config)
        self.config = raw_config

        # Resource references
        self.namespace: Optional[object] = None
        self.resource_quota: Optional[object] = None
        self.limit_range: Optional[object] = None
        self.network_policy: Optional[object] = None

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
        """Deploy Namespace Setup infrastructure (implements abstract method)"""
        return self.create()

    def create(self) -> Dict[str, Any]:
        """Deploy Namespace with ResourceQuota, LimitRange, and NetworkPolicy"""

        # Read config
        namespace_name = self._cfg('namespace_name', 'team-namespace')
        environment = self._cfg('environment', 'dev')
        project_name = self._cfg('project_name', 'namespace-app')
        team_name = self._cfg('team_name', '')

        # ResourceQuota settings
        quota_cpu = self._cfg('quota_cpu', '4')
        quota_memory = self._cfg('quota_memory', '8Gi')
        quota_pods = int(self._cfg('quota_pods', 20))
        quota_services = int(self._cfg('quota_services', 10))
        quota_pvcs = int(self._cfg('quota_pvcs', 10))

        # LimitRange settings
        default_cpu_limit = self._cfg('default_cpu_limit', '500m')
        default_cpu_request = self._cfg('default_cpu_request', '100m')
        default_memory_limit = self._cfg('default_memory_limit', '512Mi')
        default_memory_request = self._cfg('default_memory_request', '128Mi')
        max_cpu = self._cfg('max_cpu', '2')
        max_memory = self._cfg('max_memory', '4Gi')

        # Feature toggles
        enable_resource_quota = self._cfg('enable_resource_quota', True)
        enable_limit_range = self._cfg('enable_limit_range', True)
        enable_network_policy = self._cfg('enable_network_policy', True)

        if isinstance(enable_resource_quota, str):
            enable_resource_quota = enable_resource_quota.lower() in ('true', '1', 'yes')
        if isinstance(enable_limit_range, str):
            enable_limit_range = enable_limit_range.lower() in ('true', '1', 'yes')
        if isinstance(enable_network_policy, str):
            enable_network_policy = enable_network_policy.lower() in ('true', '1', 'yes')

        # Standard labels
        labels = {
            "app.kubernetes.io/managed-by": "archie",
            "app.kubernetes.io/part-of": project_name,
            "archie/environment": environment,
            "archie/project": project_name,
        }
        if team_name:
            labels["archie/team"] = team_name

        # =================================================================
        # LAYER 1: Namespace
        # =================================================================

        self.namespace = factory.create(
            "kubernetes:core/v1:Namespace",
            namespace_name,
            metadata={
                "name": namespace_name,
                "labels": labels,
                "annotations": {
                    "archie.io/managed": "true",
                    "archie.io/environment": environment,
                },
            },
        )

        # =================================================================
        # LAYER 2: ResourceQuota
        # =================================================================

        if enable_resource_quota:
            self.resource_quota = factory.create(
                "kubernetes:core/v1:ResourceQuota",
                f"{namespace_name}-quota",
                metadata={
                    "name": f"{namespace_name}-quota",
                    "namespace": namespace_name,
                    "labels": labels,
                },
                spec={
                    "hard": {
                        "limits.cpu": quota_cpu,
                        "limits.memory": quota_memory,
                        "pods": str(quota_pods),
                        "services": str(quota_services),
                        "persistentvolumeclaims": str(quota_pvcs),
                    },
                },
            )

        # =================================================================
        # LAYER 3: LimitRange
        # =================================================================

        if enable_limit_range:
            self.limit_range = factory.create(
                "kubernetes:core/v1:LimitRange",
                f"{namespace_name}-limits",
                metadata={
                    "name": f"{namespace_name}-limits",
                    "namespace": namespace_name,
                    "labels": labels,
                },
                spec={
                    "limits": [{
                        "type": "Container",
                        "default": {
                            "cpu": default_cpu_limit,
                            "memory": default_memory_limit,
                        },
                        "default_request": {
                            "cpu": default_cpu_request,
                            "memory": default_memory_request,
                        },
                        "max": {
                            "cpu": max_cpu,
                            "memory": max_memory,
                        },
                    }],
                },
            )

        # =================================================================
        # LAYER 4: NetworkPolicy (default deny ingress)
        # =================================================================

        if enable_network_policy:
            self.network_policy = factory.create(
                "kubernetes:networking.k8s.io/v1:NetworkPolicy",
                f"{namespace_name}-default-deny",
                metadata={
                    "name": "default-deny-ingress",
                    "namespace": namespace_name,
                    "labels": labels,
                },
                spec={
                    "pod_selector": {},
                    "policy_types": ["Ingress"],
                },
            )

        # =================================================================
        # Outputs (Rule #2, #7)
        # =================================================================

        pulumi.export('namespace_name', namespace_name)
        pulumi.export('environment', environment)
        pulumi.export('quota_cpu', quota_cpu)
        pulumi.export('quota_memory', quota_memory)
        pulumi.export('quota_pods', quota_pods)
        pulumi.export('resource_quota_enabled', enable_resource_quota)
        pulumi.export('limit_range_enabled', enable_limit_range)
        pulumi.export('network_policy_enabled', enable_network_policy)

        return self.get_outputs()

    def get_outputs(self) -> Dict[str, Any]:
        """Get template outputs"""
        namespace_name = self._cfg('namespace_name', 'team-namespace')
        return {
            "namespace_name": namespace_name,
            "resource_quota_name": f"{namespace_name}-quota",
            "limit_range_name": f"{namespace_name}-limits",
            "network_policy_name": "default-deny-ingress",
        }

    @classmethod
    def get_metadata(cls) -> Dict[str, Any]:
        """Template metadata for catalog UI"""
        return {
            "name": "kubernetes-namespace-setup",
            "title": "Governed Namespace Setup",
            "description": "Create a Kubernetes namespace with ResourceQuota, LimitRange, and default-deny NetworkPolicy for team isolation and governance.",
            "category": "security",
            "version": "1.0.0",
            "author": "Archie",
            "cloud": "kubernetes",
            "environment": "nonprod",
            "base_cost": "$0/month",
            "features": [
                "Namespace with governance labels and annotations",
                "ResourceQuota for CPU, memory, pod, service, and PVC limits",
                "LimitRange with default and max container resources",
                "Default-deny NetworkPolicy for ingress isolation",
                "All governance resources individually toggleable",
                "Team and environment labeling",
            ],
            "tags": ["kubernetes", "namespace", "governance", "quota", "security", "networkpolicy"],
            "deployment_time": "1 minute",
            "complexity": "beginner",
            "use_cases": [
                "Team namespace isolation with resource budgets",
                "Multi-tenant cluster governance",
                "Developer sandbox environments",
                "Compliance-ready namespace setup",
                "Cost control via resource quotas",
            ],
            "pillars": [
                {
                    "title": "Operational Excellence",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Standardized namespace setup with governance guardrails",
                    "practices": [
                        "Consistent namespace labels for discoverability and automation",
                        "ResourceQuota prevents noisy-neighbor resource exhaustion",
                        "LimitRange sets sensible defaults for all containers",
                        "Infrastructure as Code ensures repeatable namespace setup",
                        "Annotations provide metadata for tooling integration",
                    ]
                },
                {
                    "title": "Security",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Default-deny networking with resource isolation",
                    "practices": [
                        "Default-deny NetworkPolicy blocks all ingress by default",
                        "Namespace isolation separates teams and workloads",
                        "ResourceQuota prevents resource-based denial of service",
                        "LimitRange max values prevent single-container resource hogging",
                        "Labels enable fine-grained RBAC policies",
                    ]
                },
                {
                    "title": "Reliability",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Resource quotas prevent resource exhaustion that causes cascading failures",
                    "practices": [
                        "Pod count limits prevent runaway replica scaling",
                        "CPU and memory quotas ensure fair resource sharing",
                        "LimitRange defaults guarantee minimum resources per container",
                        "PVC quota prevents storage exhaustion",
                        "Service quota prevents port exhaustion",
                    ]
                },
                {
                    "title": "Performance Efficiency",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Default resource requests enable efficient scheduler placement",
                    "practices": [
                        "LimitRange defaults ensure scheduler has resource hints",
                        "Max limits prevent over-sized containers wasting resources",
                        "Resource quotas force teams to right-size workloads",
                        "Default requests enable efficient bin-packing",
                    ]
                },
                {
                    "title": "Cost Optimization",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Resource quotas enforce cost boundaries per team or environment",
                    "practices": [
                        "CPU and memory quotas cap team-level spend",
                        "Pod limits prevent uncontrolled scaling costs",
                        "PVC quotas limit storage costs",
                        "LimitRange prevents over-provisioned containers",
                    ]
                },
                {
                    "title": "Sustainability",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Resource boundaries prevent waste and over-provisioning",
                    "practices": [
                        "Quotas enforce efficient resource utilization",
                        "Default limits prevent containers from wasting compute",
                        "Namespace governance itself has zero resource footprint",
                        "Team-scoped limits encourage right-sizing",
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
                    "default": "namespace-app",
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
                "namespace_name": {
                    "type": "string",
                    "default": "team-namespace",
                    "title": "Namespace Name",
                    "description": "Name of the Kubernetes namespace to create",
                    "order": 3,
                    "group": "Essentials",
                    "isEssential": True,
                },
                "enable_resource_quota": {
                    "type": "boolean",
                    "default": True,
                    "title": "Enable ResourceQuota",
                    "description": "Create a ResourceQuota to limit total resource consumption",
                    "order": 10,
                    "group": "Architecture Decisions",
                    "cost_impact": "$0/month",
                },
                "quota_cpu": {
                    "type": "string",
                    "default": "4",
                    "title": "CPU Quota",
                    "description": "Total CPU limit for the namespace (e.g., 4, 8)",
                    "order": 11,
                    "group": "Resource Quota",
                    "conditional": {"field": "enable_resource_quota"},
                },
                "quota_memory": {
                    "type": "string",
                    "default": "8Gi",
                    "title": "Memory Quota",
                    "description": "Total memory limit for the namespace (e.g., 8Gi, 16Gi)",
                    "order": 12,
                    "group": "Resource Quota",
                    "conditional": {"field": "enable_resource_quota"},
                },
                "quota_pods": {
                    "type": "number",
                    "default": 20,
                    "title": "Pod Quota",
                    "description": "Maximum number of pods in the namespace",
                    "order": 13,
                    "group": "Resource Quota",
                    "conditional": {"field": "enable_resource_quota"},
                },
                "quota_services": {
                    "type": "number",
                    "default": 10,
                    "title": "Service Quota",
                    "description": "Maximum number of services in the namespace",
                    "order": 14,
                    "group": "Resource Quota",
                    "conditional": {"field": "enable_resource_quota"},
                },
                "quota_pvcs": {
                    "type": "number",
                    "default": 10,
                    "title": "PVC Quota",
                    "description": "Maximum number of PersistentVolumeClaims",
                    "order": 15,
                    "group": "Resource Quota",
                    "conditional": {"field": "enable_resource_quota"},
                },
                "enable_limit_range": {
                    "type": "boolean",
                    "default": True,
                    "title": "Enable LimitRange",
                    "description": "Set default and max resource limits for containers",
                    "order": 20,
                    "group": "Architecture Decisions",
                    "cost_impact": "$0/month",
                },
                "default_cpu_request": {
                    "type": "string",
                    "default": "100m",
                    "title": "Default CPU Request",
                    "description": "Default CPU request for containers without explicit request",
                    "order": 21,
                    "group": "Limit Range",
                    "conditional": {"field": "enable_limit_range"},
                },
                "default_cpu_limit": {
                    "type": "string",
                    "default": "500m",
                    "title": "Default CPU Limit",
                    "description": "Default CPU limit for containers without explicit limit",
                    "order": 22,
                    "group": "Limit Range",
                    "conditional": {"field": "enable_limit_range"},
                },
                "default_memory_request": {
                    "type": "string",
                    "default": "128Mi",
                    "title": "Default Memory Request",
                    "description": "Default memory request for containers",
                    "order": 23,
                    "group": "Limit Range",
                    "conditional": {"field": "enable_limit_range"},
                },
                "default_memory_limit": {
                    "type": "string",
                    "default": "512Mi",
                    "title": "Default Memory Limit",
                    "description": "Default memory limit for containers",
                    "order": 24,
                    "group": "Limit Range",
                    "conditional": {"field": "enable_limit_range"},
                },
                "max_cpu": {
                    "type": "string",
                    "default": "2",
                    "title": "Max CPU per Container",
                    "description": "Maximum CPU any single container can request",
                    "order": 25,
                    "group": "Limit Range",
                    "conditional": {"field": "enable_limit_range"},
                },
                "max_memory": {
                    "type": "string",
                    "default": "4Gi",
                    "title": "Max Memory per Container",
                    "description": "Maximum memory any single container can request",
                    "order": 26,
                    "group": "Limit Range",
                    "conditional": {"field": "enable_limit_range"},
                },
                "enable_network_policy": {
                    "type": "boolean",
                    "default": True,
                    "title": "Enable Default-Deny NetworkPolicy",
                    "description": "Block all ingress traffic by default (requires explicit allow rules)",
                    "order": 30,
                    "group": "Architecture Decisions",
                    "cost_impact": "$0/month",
                },
                "team_name": {
                    "type": "string",
                    "default": "",
                    "title": "Team Name",
                    "description": "Team that owns this namespace",
                    "order": 50,
                    "group": "Tags",
                },
            },
            "required": ["namespace_name"],
        }
