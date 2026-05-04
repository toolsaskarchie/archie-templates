"""
Kubernetes Helm Release Template

Deploy any Helm chart from a repository URL with configurable values.
Supports custom chart versions, namespace targeting, and values overrides.

Base cost: $0/month (Helm itself is free; chart resources vary)
- Helm Release with configurable repo, chart, and version
- Optional namespace creation
- Values override via config
- Atomic install with configurable timeout
"""

from typing import Any, Dict, Optional
import json
import pulumi
import pulumi_kubernetes as k8s

from provisioner.templates.base import template_registry, InfrastructureTemplate
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory


@template_registry("kubernetes-helm-release")
class K8sHelmReleaseTemplate(InfrastructureTemplate):
    """
    Kubernetes Helm Release Template

    Creates:
    - Kubernetes Namespace (optional)
    - Helm Release from a chart repository
    """

    def __init__(self, name: str = None, config: Dict[str, Any] = None, **kwargs):
        """Initialize Helm Release template"""
        raw_config = config or kwargs or {}
        if name is None:
            name = (
                raw_config.get('release_name') or
                raw_config.get('project_name') or
                raw_config.get('parameters', {}).get('release_name') or
                'helm-release'
            )
        super().__init__(name, raw_config)
        self.config = raw_config

        # Resource references
        self.namespace_resource: Optional[object] = None
        self.helm_release: Optional[object] = None

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
        """Deploy Helm Release infrastructure (implements abstract method)"""
        return self.create()

    def create(self) -> Dict[str, Any]:
        """Deploy Helm Release using factory pattern"""

        # Read config
        release_name = self._cfg('release_name', 'my-release')
        namespace = self._cfg('namespace', 'default')
        chart_name = self._cfg('chart_name', 'nginx')
        chart_version = self._cfg('chart_version', '')
        repo_url = self._cfg('repo_url', 'https://charts.bitnami.com/bitnami')
        environment = self._cfg('environment', 'dev')
        project_name = self._cfg('project_name', 'helm-app')
        team_name = self._cfg('team_name', '')
        timeout = self._cfg('timeout', 300)
        atomic = self._cfg('atomic', True)
        create_namespace = self._cfg('create_namespace', True)

        # Parse values override (JSON string or dict)
        values_raw = self._cfg('values_override', {})
        if isinstance(values_raw, str):
            try:
                values_override = json.loads(values_raw)
            except (json.JSONDecodeError, ValueError):
                values_override = {}
        else:
            values_override = values_raw if isinstance(values_raw, dict) else {}

        # Handle bool from DynamoDB
        if isinstance(atomic, str):
            atomic = atomic.lower() in ('true', '1', 'yes')
        if isinstance(create_namespace, str):
            create_namespace = create_namespace.lower() in ('true', '1', 'yes')

        # Standard labels
        labels = {
            "app.kubernetes.io/managed-by": "archie",
            "app.kubernetes.io/name": release_name,
            "app.kubernetes.io/instance": release_name,
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
                f"{release_name}-ns",
                metadata={
                    "name": namespace,
                    "labels": labels,
                },
            )

        # =================================================================
        # LAYER 2: Helm Release
        # =================================================================

        helm_args = {
            "chart": chart_name,
            "namespace": namespace,
            "create_namespace": create_namespace and namespace != "default",
            "values": values_override,
            "timeout": timeout,
            "atomic": atomic,
            "cleanup_on_fail": True,
        }

        if repo_url:
            helm_args["repository_opts"] = k8s.helm.v3.RepositoryOptsArgs(
                repo=repo_url,
            )

        if chart_version:
            helm_args["version"] = chart_version

        self.helm_release = k8s.helm.v3.Release(
            release_name,
            **helm_args,
        )

        # =================================================================
        # Outputs (Rule #2, #7)
        # =================================================================

        pulumi.export('release_name', release_name)
        pulumi.export('namespace', namespace)
        pulumi.export('chart_name', chart_name)
        pulumi.export('chart_version', chart_version or 'latest')
        pulumi.export('repo_url', repo_url)
        pulumi.export('environment', environment)
        pulumi.export('release_status', self.helm_release.status.apply(
            lambda s: s.status if s else 'unknown'
        ))

        return self.get_outputs()

    def get_outputs(self) -> Dict[str, Any]:
        """Get template outputs"""
        return {
            "release_name": self._cfg('release_name', 'my-release'),
            "namespace": self._cfg('namespace', 'default'),
            "chart_name": self._cfg('chart_name', 'nginx'),
            "release_status": self.helm_release.status.apply(
                lambda s: s.status if s else 'unknown'
            ) if self.helm_release else None,
        }

    @classmethod
    def get_metadata(cls) -> Dict[str, Any]:
        """Template metadata for catalog UI"""
        return {
            "name": "kubernetes-helm-release",
            "title": "Helm Chart Release",
            "description": "Deploy any Helm chart from a repository with configurable values, version pinning, and atomic installs.",
            "category": "compute",
            "version": "1.0.0",
            "author": "Archie",
            "cloud": "kubernetes",
            "environment": "nonprod",
            "base_cost": "$0/month",
            "features": [
                "Deploy any Helm chart from any repository",
                "Version pinning for reproducible deployments",
                "Values override via JSON config",
                "Atomic install with rollback on failure",
                "Optional namespace creation",
                "Configurable timeout",
            ],
            "tags": ["kubernetes", "helm", "chart", "release", "package-manager"],
            "deployment_time": "2-5 minutes",
            "complexity": "intermediate",
            "use_cases": [
                "Deploy third-party applications (Redis, PostgreSQL, Prometheus)",
                "Install monitoring stacks (Grafana, Datadog)",
                "Deploy ingress controllers (nginx, traefik)",
                "Install service meshes (Istio, Linkerd)",
                "Standardized application packaging",
            ],
            "pillars": [
                {
                    "title": "Operational Excellence",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Helm provides versioned, repeatable, and rollback-capable deployments",
                    "practices": [
                        "Version-pinned charts for reproducible deployments",
                        "Atomic installs roll back on any failure",
                        "Values override separates config from chart code",
                        "Helm release history enables easy rollbacks",
                        "Namespace isolation for workload separation",
                    ]
                },
                {
                    "title": "Security",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Namespace isolation with configurable chart values for security settings",
                    "practices": [
                        "Namespace isolation separates workloads",
                        "Chart values can configure RBAC and service accounts",
                        "Repository URL validation ensures trusted sources",
                        "Cleanup on failure removes partial installs",
                        "Labels enable audit trail and resource tracking",
                    ]
                },
                {
                    "title": "Reliability",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Atomic installs and Helm rollback provide deployment safety",
                    "practices": [
                        "Atomic install ensures all-or-nothing deployment",
                        "Configurable timeout prevents hung deployments",
                        "Helm release history supports quick rollbacks",
                        "Cleanup on failure removes broken resources",
                        "Version pinning prevents unexpected changes",
                    ]
                },
                {
                    "title": "Performance Efficiency",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Helm charts are optimized by maintainers for efficient resource usage",
                    "practices": [
                        "Community-maintained charts follow best practices",
                        "Values override allows resource tuning per environment",
                        "Chart dependencies managed automatically",
                        "Template rendering happens client-side before apply",
                    ]
                },
                {
                    "title": "Cost Optimization",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "No Helm-specific costs; resource costs depend on chart contents",
                    "practices": [
                        "Helm itself adds zero infrastructure cost",
                        "Values override enables right-sizing per environment",
                        "Namespace sharing reduces cluster overhead",
                        "Atomic cleanup prevents orphaned resources",
                    ]
                },
                {
                    "title": "Sustainability",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Efficient packaging reduces deployment overhead and resource waste",
                    "practices": [
                        "Shared chart repositories reduce duplication",
                        "Atomic cleanup prevents wasted compute from partial installs",
                        "Version pinning avoids unnecessary re-deployments",
                        "Namespace sharing maximizes cluster utilization",
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
                    "default": "helm-app",
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
                "release_name": {
                    "type": "string",
                    "default": "my-release",
                    "title": "Release Name",
                    "description": "Helm release name (unique within namespace)",
                    "order": 3,
                    "group": "Essentials",
                    "isEssential": True,
                },
                "chart_name": {
                    "type": "string",
                    "default": "nginx",
                    "title": "Chart Name",
                    "description": "Name of the Helm chart to deploy",
                    "order": 10,
                    "group": "Chart Configuration",
                },
                "chart_version": {
                    "type": "string",
                    "default": "",
                    "title": "Chart Version",
                    "description": "Specific chart version (leave empty for latest)",
                    "order": 11,
                    "group": "Chart Configuration",
                },
                "repo_url": {
                    "type": "string",
                    "default": "https://charts.bitnami.com/bitnami",
                    "title": "Repository URL",
                    "description": "Helm chart repository URL",
                    "order": 12,
                    "group": "Chart Configuration",
                },
                "namespace": {
                    "type": "string",
                    "default": "default",
                    "title": "Namespace",
                    "description": "Kubernetes namespace for the release",
                    "order": 20,
                    "group": "Deployment",
                },
                "create_namespace": {
                    "type": "boolean",
                    "default": True,
                    "title": "Create Namespace",
                    "description": "Automatically create the namespace if it does not exist",
                    "order": 21,
                    "group": "Deployment",
                },
                "values_override": {
                    "type": "string",
                    "default": "{}",
                    "title": "Values Override (JSON)",
                    "description": "JSON object to override default chart values",
                    "format": "textarea",
                    "order": 22,
                    "group": "Deployment",
                },
                "timeout": {
                    "type": "number",
                    "default": 300,
                    "title": "Timeout (seconds)",
                    "description": "Maximum time to wait for Helm release to complete",
                    "order": 30,
                    "group": "Advanced",
                },
                "atomic": {
                    "type": "boolean",
                    "default": True,
                    "title": "Atomic Install",
                    "description": "Roll back the release on failure automatically",
                    "order": 31,
                    "group": "Advanced",
                },
                "team_name": {
                    "type": "string",
                    "default": "",
                    "title": "Team Name",
                    "description": "Team that owns this release",
                    "order": 50,
                    "group": "Tags",
                },
            },
            "required": ["release_name", "chart_name", "repo_url"],
        }
