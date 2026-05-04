"""
Kubernetes HorizontalPodAutoscaler Template

Create an HPA targeting a Deployment with configurable CPU and memory thresholds.
Automatically scales pods up and down based on observed resource utilization.

Base cost: $0/month (HPA is a free K8s resource; scaling adds compute costs)
- HPA targeting any Deployment
- CPU and memory utilization thresholds
- Configurable min/max replicas
- Scale-down stabilization window
"""

from typing import Any, Dict, List, Optional
import pulumi
import pulumi_kubernetes as k8s

from provisioner.templates.base import template_registry, InfrastructureTemplate
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory


@template_registry("kubernetes-hpa")
class K8sHPATemplate(InfrastructureTemplate):
    """
    Kubernetes HorizontalPodAutoscaler Template

    Creates:
    - HorizontalPodAutoscaler targeting a Deployment
    """

    def __init__(self, name: str = None, config: Dict[str, Any] = None, **kwargs):
        """Initialize HPA template"""
        raw_config = config or kwargs or {}
        if name is None:
            name = (
                raw_config.get('hpa_name') or
                raw_config.get('project_name') or
                raw_config.get('parameters', {}).get('hpa_name') or
                'hpa'
            )
        super().__init__(name, raw_config)
        self.config = raw_config

        # Resource references
        self.hpa: Optional[object] = None

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
        """Deploy HPA infrastructure (implements abstract method)"""
        return self.create()

    def create(self) -> Dict[str, Any]:
        """Deploy HorizontalPodAutoscaler"""

        # Read config
        hpa_name = self._cfg('hpa_name', 'my-hpa')
        namespace = self._cfg('namespace', 'default')
        environment = self._cfg('environment', 'dev')
        project_name = self._cfg('project_name', 'hpa-app')
        team_name = self._cfg('team_name', '')
        target_deployment = self._cfg('target_deployment', 'my-app')
        min_replicas = int(self._cfg('min_replicas', 2))
        max_replicas = int(self._cfg('max_replicas', 10))
        cpu_utilization = int(self._cfg('cpu_utilization', 70))
        enable_memory_metric = self._cfg('enable_memory_metric', False)
        memory_utilization = int(self._cfg('memory_utilization', 80))
        scale_down_stabilization = int(self._cfg('scale_down_stabilization', 300))

        if isinstance(enable_memory_metric, str):
            enable_memory_metric = enable_memory_metric.lower() in ('true', '1', 'yes')

        # Standard labels
        labels = {
            "app.kubernetes.io/managed-by": "archie",
            "app.kubernetes.io/name": hpa_name,
            "app.kubernetes.io/component": "hpa",
            "archie/environment": environment,
            "archie/project": project_name,
        }
        if team_name:
            labels["archie/team"] = team_name

        # =================================================================
        # LAYER 1: HPA Metrics
        # =================================================================

        metrics = [
            {
                "type": "Resource",
                "resource": {
                    "name": "cpu",
                    "target": {
                        "type": "Utilization",
                        "average_utilization": cpu_utilization,
                    },
                },
            },
        ]

        if enable_memory_metric:
            metrics.append({
                "type": "Resource",
                "resource": {
                    "name": "memory",
                    "target": {
                        "type": "Utilization",
                        "average_utilization": memory_utilization,
                    },
                },
            })

        # =================================================================
        # LAYER 2: HPA
        # =================================================================

        self.hpa = factory.create(
            "kubernetes:autoscaling/v2:HorizontalPodAutoscaler",
            hpa_name,
            metadata={
                "name": hpa_name,
                "namespace": namespace,
                "labels": labels,
            },
            spec={
                "scale_target_ref": {
                    "api_version": "apps/v1",
                    "kind": "Deployment",
                    "name": target_deployment,
                },
                "min_replicas": min_replicas,
                "max_replicas": max_replicas,
                "metrics": metrics,
                "behavior": {
                    "scale_down": {
                        "stabilization_window_seconds": scale_down_stabilization,
                        "policies": [{
                            "type": "Percent",
                            "value": 10,
                            "period_seconds": 60,
                        }],
                    },
                    "scale_up": {
                        "stabilization_window_seconds": 0,
                        "policies": [{
                            "type": "Percent",
                            "value": 100,
                            "period_seconds": 15,
                        }],
                    },
                },
            },
        )

        # =================================================================
        # Outputs (Rule #2, #7)
        # =================================================================

        pulumi.export('hpa_name', hpa_name)
        pulumi.export('namespace', namespace)
        pulumi.export('target_deployment', target_deployment)
        pulumi.export('min_replicas', min_replicas)
        pulumi.export('max_replicas', max_replicas)
        pulumi.export('cpu_utilization_threshold', cpu_utilization)
        pulumi.export('environment', environment)
        if enable_memory_metric:
            pulumi.export('memory_utilization_threshold', memory_utilization)

        return self.get_outputs()

    def get_outputs(self) -> Dict[str, Any]:
        """Get template outputs"""
        return {
            "hpa_name": self._cfg('hpa_name', 'my-hpa'),
            "namespace": self._cfg('namespace', 'default'),
            "target_deployment": self._cfg('target_deployment', 'my-app'),
            "min_replicas": int(self._cfg('min_replicas', 2)),
            "max_replicas": int(self._cfg('max_replicas', 10)),
        }

    @classmethod
    def get_metadata(cls) -> Dict[str, Any]:
        """Template metadata for catalog UI"""
        return {
            "name": "kubernetes-hpa",
            "title": "HorizontalPodAutoscaler",
            "description": "Create a Kubernetes HPA targeting a Deployment with CPU and optional memory utilization thresholds, scale-down stabilization, and configurable replica bounds.",
            "category": "compute",
            "version": "1.0.0",
            "author": "Archie",
            "cloud": "kubernetes",
            "environment": "nonprod",
            "base_cost": "$0/month",
            "features": [
                "CPU utilization-based autoscaling",
                "Optional memory utilization metric",
                "Configurable min and max replicas",
                "Scale-down stabilization window to prevent flapping",
                "Aggressive scale-up policy for traffic spikes",
                "Targets any existing Deployment by name",
            ],
            "tags": ["kubernetes", "hpa", "autoscaling", "horizontal", "scaling"],
            "deployment_time": "1 minute",
            "complexity": "beginner",
            "use_cases": [
                "Auto-scale web applications under load",
                "Handle traffic spikes without manual intervention",
                "Right-size replica count during off-peak hours",
                "Cost optimization via automatic scale-down",
                "SLA compliance with responsive scaling",
            ],
            "pillars": [
                {
                    "title": "Operational Excellence",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Automated scaling removes manual replica management",
                    "practices": [
                        "Automatic replica adjustment based on real metrics",
                        "Scale-down stabilization prevents flapping",
                        "Infrastructure as Code for repeatable autoscaling config",
                        "Labels enable monitoring and alerting on scaling events",
                        "Configurable thresholds per environment",
                    ]
                },
                {
                    "title": "Security",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Max replica limit prevents runaway scaling attacks",
                    "practices": [
                        "Max replicas cap prevents unbounded pod creation",
                        "Namespace-scoped HPA limits blast radius",
                        "Labels enable RBAC targeting for HPA management",
                        "Scale-down policy prevents rapid teardown",
                    ]
                },
                {
                    "title": "Reliability",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Automatic scaling maintains availability under varying load",
                    "practices": [
                        "Scales up automatically during traffic spikes",
                        "Min replicas ensure baseline availability",
                        "Multiple metrics prevent single-metric blind spots",
                        "Stabilization prevents thrashing under fluctuating load",
                        "Kubernetes controller ensures HPA is always active",
                    ]
                },
                {
                    "title": "Performance Efficiency",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Resources match demand automatically without manual tuning",
                    "practices": [
                        "CPU-based scaling matches compute to demand",
                        "Memory-based scaling handles memory-intensive workloads",
                        "Aggressive scale-up responds quickly to spikes",
                        "Gradual scale-down prevents premature resource removal",
                    ]
                },
                {
                    "title": "Cost Optimization",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Automatic scale-down reduces costs during low-demand periods",
                    "practices": [
                        "Scale-down during off-peak reduces running pod count",
                        "Min replicas prevent over-scaling for low-traffic apps",
                        "HPA itself has zero compute cost",
                        "Right-sized replicas maximize cluster utilization",
                    ]
                },
                {
                    "title": "Sustainability",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Compute consumption matches actual demand",
                    "practices": [
                        "Automatic scale-down reduces idle compute resources",
                        "Right-sized replicas minimize energy waste",
                        "HPA metadata has zero resource footprint",
                        "Efficient scaling reduces unnecessary node provisioning",
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
                    "default": "hpa-app",
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
                "hpa_name": {
                    "type": "string",
                    "default": "my-hpa",
                    "title": "HPA Name",
                    "description": "HorizontalPodAutoscaler resource name",
                    "order": 3,
                    "group": "Essentials",
                    "isEssential": True,
                },
                "target_deployment": {
                    "type": "string",
                    "default": "my-app",
                    "title": "Target Deployment",
                    "description": "Name of the Deployment to autoscale",
                    "order": 4,
                    "group": "Essentials",
                    "isEssential": True,
                },
                "namespace": {
                    "type": "string",
                    "default": "default",
                    "title": "Namespace",
                    "description": "Namespace of the target Deployment",
                    "order": 5,
                    "group": "Essentials",
                    "isEssential": True,
                },
                "min_replicas": {
                    "type": "number",
                    "default": 2,
                    "title": "Min Replicas",
                    "description": "Minimum number of pods (never scales below this)",
                    "minimum": 1,
                    "order": 10,
                    "group": "Scaling",
                },
                "max_replicas": {
                    "type": "number",
                    "default": 10,
                    "title": "Max Replicas",
                    "description": "Maximum number of pods (never scales above this)",
                    "minimum": 1,
                    "maximum": 100,
                    "order": 11,
                    "group": "Scaling",
                    "cost_impact": "Up to max_replicas * pod cost",
                },
                "cpu_utilization": {
                    "type": "number",
                    "default": 70,
                    "title": "CPU Target (%)",
                    "description": "Average CPU utilization threshold to trigger scaling",
                    "minimum": 10,
                    "maximum": 95,
                    "order": 12,
                    "group": "Scaling",
                },
                "enable_memory_metric": {
                    "type": "boolean",
                    "default": False,
                    "title": "Enable Memory Metric",
                    "description": "Also scale based on memory utilization",
                    "order": 13,
                    "group": "Architecture Decisions",
                    "cost_impact": "$0/month",
                },
                "memory_utilization": {
                    "type": "number",
                    "default": 80,
                    "title": "Memory Target (%)",
                    "description": "Average memory utilization threshold",
                    "minimum": 10,
                    "maximum": 95,
                    "order": 14,
                    "group": "Scaling",
                    "conditional": {"field": "enable_memory_metric"},
                },
                "scale_down_stabilization": {
                    "type": "number",
                    "default": 300,
                    "title": "Scale-Down Stabilization (seconds)",
                    "description": "Cooldown period before scaling down (prevents flapping)",
                    "minimum": 0,
                    "maximum": 3600,
                    "order": 20,
                    "group": "Advanced",
                },
                "team_name": {
                    "type": "string",
                    "default": "",
                    "title": "Team Name",
                    "description": "Team that owns the target workload",
                    "order": 50,
                    "group": "Tags",
                },
            },
            "required": ["hpa_name", "target_deployment", "namespace"],
        }
