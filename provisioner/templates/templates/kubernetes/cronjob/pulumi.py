"""
Kubernetes CronJob Template

Deploy a CronJob with configurable schedule, image, and command.
Ideal for batch processing, data pipelines, backups, and periodic tasks.

Base cost: $0/month (compute costs only when jobs run)
- CronJob with cron schedule expression
- Configurable container image and command
- Job history limits and concurrency policy
- Restart policy and backoff limits
"""

from typing import Any, Dict, List, Optional
import pulumi
import pulumi_kubernetes as k8s

from provisioner.templates.base import template_registry, InfrastructureTemplate
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory


@template_registry("kubernetes-cronjob")
class K8sCronJobTemplate(InfrastructureTemplate):
    """
    Kubernetes CronJob Template

    Creates:
    - Kubernetes Namespace (optional)
    - CronJob with schedule, image, command
    """

    def __init__(self, name: str = None, config: Dict[str, Any] = None, **kwargs):
        """Initialize CronJob template"""
        raw_config = config or kwargs or {}
        if name is None:
            name = (
                raw_config.get('job_name') or
                raw_config.get('project_name') or
                raw_config.get('parameters', {}).get('job_name') or
                'cronjob'
            )
        super().__init__(name, raw_config)
        self.config = raw_config

        # Resource references
        self.namespace_resource: Optional[object] = None
        self.cronjob: Optional[object] = None

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
        """Deploy CronJob infrastructure (implements abstract method)"""
        return self.create()

    def create(self) -> Dict[str, Any]:
        """Deploy CronJob using factory pattern"""

        # Read config
        job_name = self._cfg('job_name', 'my-cronjob')
        namespace = self._cfg('namespace', 'default')
        environment = self._cfg('environment', 'dev')
        project_name = self._cfg('project_name', 'cronjob-app')
        team_name = self._cfg('team_name', '')
        image = self._cfg('image', 'busybox:1.36')
        schedule = self._cfg('schedule', '0 */6 * * *')
        command_str = self._cfg('command', '/bin/sh,-c,echo "Hello from CronJob"')
        cpu_request = self._cfg('cpu_request', '100m')
        cpu_limit = self._cfg('cpu_limit', '250m')
        memory_request = self._cfg('memory_request', '128Mi')
        memory_limit = self._cfg('memory_limit', '256Mi')
        restart_policy = self._cfg('restart_policy', 'OnFailure')
        backoff_limit = int(self._cfg('backoff_limit', 3))
        concurrency_policy = self._cfg('concurrency_policy', 'Forbid')
        successful_jobs_history = int(self._cfg('successful_jobs_history', 3))
        failed_jobs_history = int(self._cfg('failed_jobs_history', 1))
        active_deadline_seconds = int(self._cfg('active_deadline_seconds', 600))
        suspend = self._cfg('suspend', False)

        create_namespace = self._cfg('create_namespace', True)
        if isinstance(create_namespace, str):
            create_namespace = create_namespace.lower() in ('true', '1', 'yes')
        if isinstance(suspend, str):
            suspend = suspend.lower() in ('true', '1', 'yes')

        # Parse command string into list
        if isinstance(command_str, str):
            command = [c.strip() for c in command_str.split(',')]
        elif isinstance(command_str, list):
            command = command_str
        else:
            command = ['/bin/sh', '-c', 'echo "Hello from CronJob"']

        # Standard labels
        labels = {
            "app.kubernetes.io/managed-by": "archie",
            "app.kubernetes.io/name": job_name,
            "app.kubernetes.io/component": "cronjob",
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
                f"{job_name}-ns",
                metadata={
                    "name": namespace,
                    "labels": labels,
                },
            )

        # =================================================================
        # LAYER 2: CronJob
        # =================================================================

        self.cronjob = factory.create(
            "kubernetes:batch/v1:CronJob",
            job_name,
            metadata={
                "name": job_name,
                "namespace": namespace,
                "labels": labels,
            },
            spec={
                "schedule": schedule,
                "concurrency_policy": concurrency_policy,
                "successful_jobs_history_limit": successful_jobs_history,
                "failed_jobs_history_limit": failed_jobs_history,
                "suspend": suspend,
                "job_template": {
                    "spec": {
                        "backoff_limit": backoff_limit,
                        "active_deadline_seconds": active_deadline_seconds,
                        "template": {
                            "metadata": {
                                "labels": {
                                    **labels,
                                    "app.kubernetes.io/name": job_name,
                                },
                            },
                            "spec": {
                                "restart_policy": restart_policy,
                                "containers": [{
                                    "name": job_name,
                                    "image": image,
                                    "command": command,
                                    "resources": {
                                        "limits": {"cpu": cpu_limit, "memory": memory_limit},
                                        "requests": {"cpu": cpu_request, "memory": memory_request},
                                    },
                                }],
                            },
                        },
                    },
                },
            },
        )

        # =================================================================
        # Outputs (Rule #2, #7)
        # =================================================================

        pulumi.export('job_name', job_name)
        pulumi.export('namespace', namespace)
        pulumi.export('schedule', schedule)
        pulumi.export('image', image)
        pulumi.export('environment', environment)
        pulumi.export('concurrency_policy', concurrency_policy)

        return self.get_outputs()

    def get_outputs(self) -> Dict[str, Any]:
        """Get template outputs"""
        return {
            "job_name": self._cfg('job_name', 'my-cronjob'),
            "namespace": self._cfg('namespace', 'default'),
            "schedule": self._cfg('schedule', '0 */6 * * *'),
            "image": self._cfg('image', 'busybox:1.36'),
        }

    @classmethod
    def get_metadata(cls) -> Dict[str, Any]:
        """Template metadata for catalog UI"""
        return {
            "name": "kubernetes-cronjob",
            "title": "CronJob Scheduled Task",
            "description": "Deploy a Kubernetes CronJob with configurable schedule, image, command, concurrency policy, and job history limits.",
            "category": "compute",
            "version": "1.0.0",
            "author": "Archie",
            "cloud": "kubernetes",
            "environment": "nonprod",
            "base_cost": "$0/month",
            "features": [
                "Cron schedule expression for flexible timing",
                "Configurable container image and command",
                "Concurrency policy (Forbid, Allow, Replace)",
                "Job history limits for successful and failed jobs",
                "Active deadline and backoff limits",
                "Suspend toggle to pause scheduling",
            ],
            "tags": ["kubernetes", "cronjob", "batch", "scheduled", "cron"],
            "deployment_time": "1-2 minutes",
            "complexity": "beginner",
            "use_cases": [
                "Database backups on a schedule",
                "Data pipeline ETL jobs",
                "Log rotation and cleanup",
                "Report generation",
                "Health checks and monitoring probes",
            ],
            "pillars": [
                {
                    "title": "Operational Excellence",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Declarative scheduling with configurable history and concurrency controls",
                    "practices": [
                        "Cron expression for precise scheduling control",
                        "Job history limits prevent unbounded resource growth",
                        "Concurrency policy prevents overlapping executions",
                        "Active deadline prevents runaway jobs",
                        "Suspend toggle enables maintenance windows without deletion",
                    ]
                },
                {
                    "title": "Security",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Namespace isolation with resource-constrained containers",
                    "practices": [
                        "Namespace isolation separates scheduled workloads",
                        "Resource limits prevent resource exhaustion attacks",
                        "Short-lived containers reduce attack surface",
                        "Labels enable RBAC targeting for CronJob permissions",
                        "Restart policy controls failure handling behavior",
                    ]
                },
                {
                    "title": "Reliability",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Backoff limits and restart policy ensure job completion",
                    "practices": [
                        "Backoff limit retries failed jobs automatically",
                        "Active deadline prevents infinite execution",
                        "Concurrency policy prevents resource contention",
                        "Kubernetes reschedules on node failures",
                        "Failed job history aids in debugging",
                    ]
                },
                {
                    "title": "Performance Efficiency",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Resources consumed only during job execution",
                    "practices": [
                        "Pods created on schedule and terminated on completion",
                        "Resource requests ensure guaranteed compute during execution",
                        "No idle resource consumption between runs",
                        "Configurable parallelism for throughput tuning",
                    ]
                },
                {
                    "title": "Cost Optimization",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Zero cost between runs; compute only when executing",
                    "practices": [
                        "Pods terminated after completion — no idle costs",
                        "Job history limits prevent storage waste",
                        "Resource requests enable bin-packing on shared nodes",
                        "Suspend toggle stops scheduling without deletion",
                    ]
                },
                {
                    "title": "Sustainability",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Minimal resource footprint with on-demand execution",
                    "practices": [
                        "No long-running pods — compute used only when needed",
                        "Job history cleanup reduces storage footprint",
                        "Shared cluster nodes maximize utilization",
                        "Short-lived containers minimize energy consumption",
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
                    "default": "cronjob-app",
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
                "job_name": {
                    "type": "string",
                    "default": "my-cronjob",
                    "title": "Job Name",
                    "description": "CronJob resource name",
                    "order": 3,
                    "group": "Essentials",
                    "isEssential": True,
                },
                "schedule": {
                    "type": "string",
                    "default": "0 */6 * * *",
                    "title": "Schedule (Cron)",
                    "description": "Cron expression (e.g., '*/5 * * * *' for every 5 min, '0 2 * * *' for daily at 2am)",
                    "order": 10,
                    "group": "Schedule",
                },
                "image": {
                    "type": "string",
                    "default": "busybox:1.36",
                    "title": "Container Image",
                    "description": "Docker image for the job container",
                    "order": 11,
                    "group": "Container",
                },
                "command": {
                    "type": "string",
                    "default": "/bin/sh,-c,echo \"Hello from CronJob\"",
                    "title": "Command",
                    "description": "Comma-separated command (e.g., /bin/sh,-c,python backup.py)",
                    "order": 12,
                    "group": "Container",
                },
                "cpu_request": {
                    "type": "string",
                    "default": "100m",
                    "title": "CPU Request",
                    "description": "Guaranteed CPU per job pod",
                    "order": 13,
                    "group": "Container",
                },
                "cpu_limit": {
                    "type": "string",
                    "default": "250m",
                    "title": "CPU Limit",
                    "description": "Maximum CPU per job pod",
                    "order": 14,
                    "group": "Container",
                },
                "memory_request": {
                    "type": "string",
                    "default": "128Mi",
                    "title": "Memory Request",
                    "description": "Guaranteed memory per job pod",
                    "order": 15,
                    "group": "Container",
                },
                "memory_limit": {
                    "type": "string",
                    "default": "256Mi",
                    "title": "Memory Limit",
                    "description": "Maximum memory per job pod",
                    "order": 16,
                    "group": "Container",
                },
                "concurrency_policy": {
                    "type": "string",
                    "default": "Forbid",
                    "title": "Concurrency Policy",
                    "description": "How to handle concurrent job executions",
                    "enum": ["Allow", "Forbid", "Replace"],
                    "order": 20,
                    "group": "Job Settings",
                },
                "backoff_limit": {
                    "type": "number",
                    "default": 3,
                    "title": "Backoff Limit",
                    "description": "Number of retries before marking job as failed",
                    "order": 21,
                    "group": "Job Settings",
                },
                "active_deadline_seconds": {
                    "type": "number",
                    "default": 600,
                    "title": "Active Deadline (seconds)",
                    "description": "Maximum runtime before the job is terminated",
                    "order": 22,
                    "group": "Job Settings",
                },
                "restart_policy": {
                    "type": "string",
                    "default": "OnFailure",
                    "title": "Restart Policy",
                    "description": "Pod restart behavior on failure",
                    "enum": ["OnFailure", "Never"],
                    "order": 23,
                    "group": "Job Settings",
                },
                "successful_jobs_history": {
                    "type": "number",
                    "default": 3,
                    "title": "Successful Job History",
                    "description": "Number of successful jobs to retain",
                    "order": 24,
                    "group": "Job Settings",
                },
                "failed_jobs_history": {
                    "type": "number",
                    "default": 1,
                    "title": "Failed Job History",
                    "description": "Number of failed jobs to retain",
                    "order": 25,
                    "group": "Job Settings",
                },
                "suspend": {
                    "type": "boolean",
                    "default": False,
                    "title": "Suspend",
                    "description": "Pause the CronJob schedule without deleting it",
                    "order": 26,
                    "group": "Job Settings",
                },
                "namespace": {
                    "type": "string",
                    "default": "default",
                    "title": "Namespace",
                    "description": "Kubernetes namespace for the CronJob",
                    "order": 30,
                    "group": "Deployment",
                },
                "team_name": {
                    "type": "string",
                    "default": "",
                    "title": "Team Name",
                    "description": "Team that owns this job",
                    "order": 50,
                    "group": "Tags",
                },
            },
            "required": ["job_name", "schedule", "image"],
        }
