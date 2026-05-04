"""
GCP Cloud Run Non-Prod Template

Serverless container service for development and testing:
- Cloud Run service with configurable container image
- IAM invoker binding (allUsers or authenticated)
- Custom domain mapping ready
- Auto-scaling from 0 to configurable max

Base cost (~$0/mo idle):
- Pay per request + compute time
- Scales to zero when idle
- Free tier: 2M requests/mo, 360K vCPU-sec, 180K GiB-sec
"""

from typing import Any, Dict, Optional
import pulumi
import pulumi_gcp as gcp

from provisioner.templates.base import InfrastructureTemplate, template_registry
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory


@template_registry("gcp-cloud-run-nonprod")
class CloudRunNonprodTemplate(InfrastructureTemplate):
    """
    GCP Cloud Run Non-Prod Template

    Deploys a serverless Cloud Run service with IAM invoker binding
    and custom domain support for non-production workloads.
    """

    def __init__(self, name: str = None, config: Dict[str, Any] = None, gcp_config: Dict[str, Any] = None, **kwargs):
        """Initialize Cloud Run Non-Prod template"""
        raw_config = config or gcp_config or kwargs or {}

        if name is None:
            name = (
                raw_config.get('project_name') or
                raw_config.get('projectName') or
                raw_config.get('parameters', {}).get('gcp', {}).get('project_name') or
                'cloud-run-nonprod'
            )

        super().__init__(name, raw_config)
        self.config = raw_config

        # Resource references
        self.service: Optional[object] = None
        self.iam_member: Optional[object] = None
        self.domain_mapping: Optional[object] = None
        self.service_account: Optional[object] = None

    def _cfg(self, key: str, default=None):
        """Read config from root, parameters.gcp, or parameters (Rule #6)"""
        params = self.config.get('parameters', {})
        gcp_params = params.get('gcp', {}) if isinstance(params, dict) else {}
        return (
            self.config.get(key) or
            (gcp_params.get(key) if isinstance(gcp_params, dict) else None) or
            (params.get(key) if isinstance(params, dict) else None) or
            default
        )

    def create_infrastructure(self) -> Dict[str, Any]:
        """Deploy Cloud Run infrastructure (implements abstract method)"""
        return self.create()

    def create(self) -> Dict[str, Any]:
        """Deploy complete Cloud Run service infrastructure"""

        # Read config
        project_name = self._cfg('project_name', 'cloud-run')
        environment = self._cfg('environment', 'dev')
        team_name = self._cfg('team_name', '')
        gcp_project = self._cfg('gcp_project', '')
        region = self._cfg('region', 'us-central1')

        # Service config
        container_image = self._cfg('container_image', 'gcr.io/cloudrun/hello')
        container_port = int(self._cfg('container_port', 8080))
        memory = self._cfg('memory', '256Mi')
        cpu = self._cfg('cpu', '1')
        max_instances = int(self._cfg('max_instances', 10))
        min_instances = int(self._cfg('min_instances', 0))
        timeout_seconds = int(self._cfg('timeout_seconds', 300))
        concurrency = int(self._cfg('concurrency', 80))

        # Access config
        allow_unauthenticated = self._cfg('allow_unauthenticated', True)
        if isinstance(allow_unauthenticated, str):
            allow_unauthenticated = allow_unauthenticated.lower() in ('true', '1', 'yes')

        # Custom domain
        custom_domain = self._cfg('custom_domain', '')

        # Environment variables
        env_vars = self._cfg('env_vars', {})

        # Standard GCP labels
        labels = {
            'project': project_name,
            'environment': environment,
            'template': 'gcp-cloud-run-nonprod',
            'managed-by': 'archie',
        }
        if team_name:
            labels['team'] = team_name.lower().replace(' ', '-')
        labels.update(self._cfg('labels', {}))

        resource_name = f"{project_name}-{environment}"
        service_name = self._cfg('service_name', resource_name)

        # =================================================================
        # LAYER 1: Service Account (dedicated)
        # =================================================================

        sa_name = f"{resource_name}-run-sa"
        self.service_account = gcp.serviceaccount.Account(
            sa_name,
            account_id=sa_name[:28],  # SA ID max 28 chars
            project=gcp_project if gcp_project else None,
            display_name=f"Cloud Run SA for {resource_name}",
        )

        # =================================================================
        # LAYER 2: Cloud Run Service
        # =================================================================

        # Build environment variables list
        env_list = [
            {"name": "ENVIRONMENT", "value": environment},
            {"name": "PROJECT_NAME", "value": project_name},
        ]
        if isinstance(env_vars, dict):
            for k, v in env_vars.items():
                env_list.append({"name": k, "value": str(v)})

        self.service = gcp.cloudrun.Service(
            service_name,
            name=service_name,
            project=gcp_project if gcp_project else None,
            location=region,
            template={
                "metadata": {
                    "annotations": {
                        "autoscaling.knative.dev/maxScale": str(max_instances),
                        "autoscaling.knative.dev/minScale": str(min_instances),
                        "run.googleapis.com/cpu-throttling": "true",
                    },
                    "labels": labels,
                },
                "spec": {
                    "container_concurrency": concurrency,
                    "timeout_seconds": timeout_seconds,
                    "service_account_name": self.service_account.email,
                    "containers": [{
                        "image": container_image,
                        "ports": [{"container_port": container_port}],
                        "resources": {
                            "limits": {
                                "memory": memory,
                                "cpu": cpu,
                            },
                        },
                        "envs": env_list,
                    }],
                },
            },
            traffics=[{
                "percent": 100,
                "latest_revision": True,
            }],
            metadata={
                "labels": labels,
                "annotations": {
                    "run.googleapis.com/ingress": "all",
                },
            },
        )

        # =================================================================
        # LAYER 3: IAM Invoker Binding
        # =================================================================

        if allow_unauthenticated:
            self.iam_member = gcp.cloudrun.IamMember(
                f"{service_name}-invoker",
                project=gcp_project if gcp_project else None,
                location=region,
                service=self.service.name,
                role="roles/run.invoker",
                member="allUsers",
            )

        # =================================================================
        # LAYER 4: Custom Domain Mapping (Optional)
        # =================================================================

        if custom_domain:
            self.domain_mapping = gcp.cloudrun.DomainMapping(
                f"{service_name}-domain",
                name=custom_domain,
                project=gcp_project if gcp_project else None,
                location=region,
                metadata={
                    "namespace": gcp_project if gcp_project else None,
                },
                spec={
                    "route_name": self.service.name,
                },
            )

        # =================================================================
        # Exports (Rule #2, #7)
        # =================================================================

        pulumi.export('service_name', self.service.name)
        pulumi.export('service_id', self.service.id)
        pulumi.export('service_url', self.service.statuses.apply(
            lambda statuses: statuses[0].url if statuses and len(statuses) > 0 else None
        ))
        pulumi.export('service_account_email', self.service_account.email)
        pulumi.export('region', region)
        pulumi.export('environment', environment)
        pulumi.export('container_image', container_image)
        pulumi.export('allow_unauthenticated', str(allow_unauthenticated))

        if custom_domain:
            pulumi.export('custom_domain', custom_domain)

        return self.get_outputs()

    def get_outputs(self) -> Dict[str, Any]:
        """Get outputs for this template"""
        return {
            "service_name": self.service.name if self.service else None,
            "service_id": self.service.id if self.service else None,
            "service_url": self.service.statuses.apply(
                lambda statuses: statuses[0].url if statuses and len(statuses) > 0 else None
            ) if self.service else None,
            "service_account_email": self.service_account.email if self.service_account else None,
            "custom_domain": self.domain_mapping.name if self.domain_mapping else None,
        }

    @classmethod
    def get_metadata(cls) -> Dict[str, Any]:
        """Template metadata for the catalog UI"""
        return {
            "name": "gcp-cloud-run-nonprod",
            "title": "Cloud Run Service",
            "description": "Serverless container service with auto-scaling, IAM invoker binding, and custom domain support for non-production workloads.",
            "category": "serverless",
            "version": "1.0.0",
            "author": "Archie",
            "cloud": "gcp",
            "environment": "nonprod",
            "base_cost": "$0/month (idle)",
            "features": [
                "Cloud Run fully managed serverless containers",
                "Auto-scaling from 0 to configurable max instances",
                "Dedicated service account with least privilege",
                "IAM invoker binding (public or authenticated)",
                "Custom domain mapping support",
                "Configurable CPU, memory, and concurrency",
                "Environment variable injection",
                "100% traffic to latest revision",
                "CPU throttling enabled for cost savings",
            ],
            "tags": ["gcp", "cloud-run", "serverless", "container", "nonprod", "knative"],
            "deployment_time": "2-3 minutes",
            "complexity": "beginner",
            "use_cases": [
                "Stateless API services",
                "Web application backends",
                "Webhook handlers",
                "Background job processors",
                "Prototype and demo applications",
            ],
            "pillars": [
                {
                    "title": "Operational Excellence",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Fully managed serverless with zero infrastructure operations",
                    "practices": [
                        "Infrastructure as Code with Pulumi for repeatable deployments",
                        "Zero server management — Google handles scaling and patching",
                        "Automatic revision management with traffic splitting",
                        "Environment variables for configuration without rebuilds",
                        "Dedicated service account for clear IAM ownership",
                    ],
                },
                {
                    "title": "Security",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Dedicated service account with configurable access control",
                    "practices": [
                        "Dedicated service account per service",
                        "Configurable IAM invoker (public or authenticated only)",
                        "Container isolation via gVisor sandbox",
                        "HTTPS enforced on all Cloud Run URLs",
                        "Ingress controls configurable (all, internal, internal-and-lb)",
                    ],
                },
                {
                    "title": "Reliability",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Auto-scaling with configurable concurrency and timeout",
                    "practices": [
                        "Automatic scaling responds to traffic spikes",
                        "Health checks built into the platform",
                        "Configurable request timeout up to 3600 seconds",
                        "Revision rollback available via traffic management",
                    ],
                },
                {
                    "title": "Performance Efficiency",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Right-sized containers with configurable concurrency",
                    "practices": [
                        "Configurable CPU and memory per container",
                        "Concurrency control prevents overloading containers",
                        "Cold start optimization via min instances setting",
                        "CPU throttling reduces costs during idle periods",
                    ],
                },
                {
                    "title": "Cost Optimization",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Pay-per-use with scale-to-zero and generous free tier",
                    "practices": [
                        "Scales to zero when idle — no cost with no traffic",
                        "Free tier covers 2M requests and 360K vCPU-seconds/month",
                        "CPU throttling enabled to reduce idle compute charges",
                        "No reserved capacity or minimum commitment required",
                    ],
                },
                {
                    "title": "Sustainability",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Scale-to-zero eliminates idle resource consumption",
                    "practices": [
                        "Zero idle resources when no traffic is flowing",
                        "Shared infrastructure maximizes server utilization",
                        "Right-sized containers avoid over-provisioned compute",
                        "Google Cloud carbon-neutral infrastructure",
                    ],
                },
            ],
        }

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        """Configuration schema for the deploy form"""
        return {
            "type": "object",
            "properties": {
                "project_name": {
                    "type": "string",
                    "default": "myproject",
                    "title": "Project Name",
                    "description": "Used in resource naming (lowercase, no spaces)",
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
                "region": {
                    "type": "string",
                    "default": "us-central1",
                    "title": "GCP Region",
                    "description": "Region for Cloud Run service",
                    "enum": ["us-central1", "us-east1", "us-west1", "europe-west1", "asia-east1", "asia-northeast1"],
                    "order": 3,
                    "group": "Essentials",
                    "isEssential": True,
                },
                "gcp_project": {
                    "type": "string",
                    "default": "",
                    "title": "GCP Project ID",
                    "description": "Google Cloud project ID (leave empty to use default)",
                    "order": 4,
                    "group": "Essentials",
                    "isEssential": True,
                },
                "container_image": {
                    "type": "string",
                    "default": "gcr.io/cloudrun/hello",
                    "title": "Container Image",
                    "description": "Docker image to deploy (e.g., gcr.io/my-project/my-app:latest)",
                    "order": 10,
                    "group": "Container Configuration",
                    "isEssential": True,
                },
                "container_port": {
                    "type": "number",
                    "default": 8080,
                    "title": "Container Port",
                    "description": "Port the container listens on",
                    "order": 11,
                    "group": "Container Configuration",
                },
                "cpu": {
                    "type": "string",
                    "default": "1",
                    "title": "CPU",
                    "description": "CPU allocation per container instance",
                    "enum": ["1", "2", "4"],
                    "order": 12,
                    "group": "Container Configuration",
                    "cost_impact": "1 CPU: ~$0.00002400/sec",
                },
                "memory": {
                    "type": "string",
                    "default": "256Mi",
                    "title": "Memory",
                    "description": "Memory allocation per container instance",
                    "enum": ["128Mi", "256Mi", "512Mi", "1Gi", "2Gi", "4Gi"],
                    "order": 13,
                    "group": "Container Configuration",
                    "cost_impact": "256Mi: ~$0.00000250/sec",
                },
                "service_name": {
                    "type": "string",
                    "default": "",
                    "title": "Service Name",
                    "description": "Custom Cloud Run service name (defaults to project-env)",
                    "order": 14,
                    "group": "Container Configuration",
                },
                "max_instances": {
                    "type": "number",
                    "default": 10,
                    "title": "Max Instances",
                    "description": "Maximum number of container instances",
                    "minimum": 1,
                    "maximum": 1000,
                    "order": 20,
                    "group": "Scaling",
                },
                "min_instances": {
                    "type": "number",
                    "default": 0,
                    "title": "Min Instances",
                    "description": "Minimum instances to keep warm (0 = scale to zero)",
                    "minimum": 0,
                    "maximum": 100,
                    "order": 21,
                    "group": "Scaling",
                    "cost_impact": "Each warm instance incurs idle charges",
                },
                "concurrency": {
                    "type": "number",
                    "default": 80,
                    "title": "Concurrency",
                    "description": "Max concurrent requests per instance",
                    "minimum": 1,
                    "maximum": 1000,
                    "order": 22,
                    "group": "Scaling",
                },
                "timeout_seconds": {
                    "type": "number",
                    "default": 300,
                    "title": "Request Timeout (sec)",
                    "description": "Maximum time per request before timeout",
                    "minimum": 1,
                    "maximum": 3600,
                    "order": 23,
                    "group": "Scaling",
                },
                "allow_unauthenticated": {
                    "type": "boolean",
                    "default": True,
                    "title": "Allow Unauthenticated",
                    "description": "Allow public access without authentication",
                    "order": 30,
                    "group": "Security & Access",
                },
                "custom_domain": {
                    "type": "string",
                    "default": "",
                    "title": "Custom Domain",
                    "description": "Custom domain to map to this service (e.g., api.example.com)",
                    "order": 31,
                    "group": "Security & Access",
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
            "required": ["project_name", "region", "container_image"],
        }
