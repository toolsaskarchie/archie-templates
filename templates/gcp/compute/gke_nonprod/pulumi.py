"""
GCP GKE Autopilot Non-Prod Template

Cost-optimized Kubernetes cluster for development and testing:
- GKE Autopilot mode (Google manages node pools)
- Private cluster with private nodes
- Workload Identity enabled
- Release channel: REGULAR

Base cost (~$74/mo):
- Autopilot management fee ($0.10/vCPU/hr for autopilot overhead)
- Actual cost scales with workloads deployed
- No idle node costs (Autopilot scales to zero)
"""

from typing import Any, Dict, Optional
import pulumi
import pulumi_gcp as gcp

from provisioner.templates.base import InfrastructureTemplate, template_registry
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory


@template_registry("gcp-gke-nonprod")
class GKENonprodTemplate(InfrastructureTemplate):
    """
    GCP GKE Autopilot Non-Prod Template

    Deploys a managed Kubernetes cluster with Autopilot mode,
    private nodes, and Workload Identity for non-production workloads.
    """

    def __init__(self, name: str = None, config: Dict[str, Any] = None, gcp_config: Dict[str, Any] = None, **kwargs):
        """Initialize GKE Non-Prod template"""
        raw_config = config or gcp_config or kwargs or {}

        if name is None:
            name = (
                raw_config.get('project_name') or
                raw_config.get('projectName') or
                raw_config.get('parameters', {}).get('gcp', {}).get('project_name') or
                'gke-nonprod'
            )

        super().__init__(name, raw_config)
        self.config = raw_config

        # Resource references
        self.cluster: Optional[object] = None
        self.service_account: Optional[object] = None
        self.sa_iam_binding: Optional[object] = None
        self.firewall_allow_master: Optional[object] = None

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
        """Deploy GKE infrastructure (implements abstract method)"""
        return self.create()

    def create(self) -> Dict[str, Any]:
        """Deploy complete GKE Autopilot infrastructure"""

        # Read config
        project_name = self._cfg('project_name', 'gke')
        environment = self._cfg('environment', 'dev')
        team_name = self._cfg('team_name', '')
        gcp_project = self._cfg('gcp_project', '')
        region = self._cfg('region', 'us-central1')
        network = self._cfg('network', 'default')
        subnetwork = self._cfg('subnetwork', 'default')

        # Cluster config
        release_channel = self._cfg('release_channel', 'REGULAR')
        enable_private_nodes = self._cfg('enable_private_nodes', True)
        if isinstance(enable_private_nodes, str):
            enable_private_nodes = enable_private_nodes.lower() in ('true', '1', 'yes')
        enable_private_endpoint = self._cfg('enable_private_endpoint', False)
        if isinstance(enable_private_endpoint, str):
            enable_private_endpoint = enable_private_endpoint.lower() in ('true', '1', 'yes')
        master_cidr = self._cfg('master_ipv4_cidr', '172.16.0.0/28')
        authorized_networks = self._cfg('authorized_networks', [])

        # Standard GCP labels
        labels = {
            'project': project_name,
            'environment': environment,
            'template': 'gcp-gke-nonprod',
            'managed-by': 'archie',
        }
        if team_name:
            labels['team'] = team_name.lower().replace(' ', '-')
        labels.update(self._cfg('labels', {}))

        resource_name = f"{project_name}-{environment}"
        cluster_name = self._cfg('cluster_name', f"{resource_name}-gke")

        # =================================================================
        # LAYER 1: GKE Service Account
        # =================================================================

        sa_name = f"{resource_name}-gke-sa"
        self.service_account = gcp.serviceaccount.Account(
            sa_name,
            account_id=sa_name[:28],  # SA ID max 28 chars
            project=gcp_project if gcp_project else None,
            display_name=f"GKE Autopilot SA for {resource_name}",
        )

        # Grant minimum required roles
        sa_roles = [
            "roles/logging.logWriter",
            "roles/monitoring.metricWriter",
            "roles/monitoring.viewer",
            "roles/artifactregistry.reader",
        ]

        for i, role in enumerate(sa_roles):
            gcp.projects.IAMMember(
                f"{sa_name}-role-{i}",
                project=gcp_project if gcp_project else pulumi.Config("gcp").get("project"),
                role=role,
                member=self.service_account.email.apply(lambda email: f"serviceAccount:{email}"),
            )

        # =================================================================
        # LAYER 2: GKE Autopilot Cluster
        # =================================================================

        private_cluster_config = None
        if enable_private_nodes:
            private_cluster_config = {
                "enable_private_nodes": True,
                "enable_private_endpoint": enable_private_endpoint,
                "master_ipv4_cidr_block": master_cidr,
            }

        # Build master authorized networks config
        master_authorized_networks = None
        if authorized_networks:
            master_authorized_networks = {
                "cidr_blocks": [
                    {"cidr_block": net, "display_name": f"authorized-{i}"}
                    for i, net in enumerate(authorized_networks)
                ],
            }

        self.cluster = gcp.container.Cluster(
            cluster_name,
            name=cluster_name,
            project=gcp_project if gcp_project else None,
            location=region,
            network=network,
            subnetwork=subnetwork,
            enable_autopilot=True,
            release_channel={"channel": release_channel},
            private_cluster_config=private_cluster_config,
            master_authorized_networks_config=master_authorized_networks,
            resource_labels=labels,
            ip_allocation_policy={},  # Required for VPC-native clusters
            deletion_protection=False,
            workload_identity_config={
                "workload_pool": (
                    f"{gcp_project}.svc.id.goog" if gcp_project
                    else pulumi.Config("gcp").get("project").apply(lambda p: f"{p}.svc.id.goog")
                    if pulumi.Config("gcp").get("project")
                    else None
                ),
            },
        )

        # =================================================================
        # Exports (Rule #2, #7)
        # =================================================================

        pulumi.export('cluster_name', self.cluster.name)
        pulumi.export('cluster_id', self.cluster.id)
        pulumi.export('cluster_endpoint', self.cluster.endpoint)
        pulumi.export('cluster_ca_certificate', self.cluster.master_auth.apply(
            lambda auth: auth.cluster_ca_certificate if auth else None
        ))
        pulumi.export('cluster_location', self.cluster.location)
        pulumi.export('cluster_self_link', self.cluster.self_link)
        pulumi.export('service_account_email', self.service_account.email)
        pulumi.export('kubeconfig_cmd', pulumi.Output.concat(
            'gcloud container clusters get-credentials ', self.cluster.name,
            ' --region ', region,
            f' --project {gcp_project}' if gcp_project else '',
        ))
        pulumi.export('region', region)
        pulumi.export('environment', environment)

        return self.get_outputs()

    def get_outputs(self) -> Dict[str, Any]:
        """Get outputs for this template"""
        return {
            "cluster_name": self.cluster.name if self.cluster else None,
            "cluster_id": self.cluster.id if self.cluster else None,
            "cluster_endpoint": self.cluster.endpoint if self.cluster else None,
            "cluster_ca_certificate": self.cluster.master_auth.apply(
                lambda auth: auth.cluster_ca_certificate if auth else None
            ) if self.cluster else None,
            "cluster_location": self.cluster.location if self.cluster else None,
            "cluster_self_link": self.cluster.self_link if self.cluster else None,
            "service_account_email": self.service_account.email if self.service_account else None,
        }

    @classmethod
    def get_metadata(cls) -> Dict[str, Any]:
        """Template metadata for the catalog UI"""
        return {
            "name": "gcp-gke-nonprod",
            "title": "GKE Autopilot Cluster",
            "description": "Managed Kubernetes cluster with Autopilot mode, private nodes, and Workload Identity for non-production workloads.",
            "category": "kubernetes",
            "version": "1.0.0",
            "author": "Archie",
            "cloud": "gcp",
            "environment": "nonprod",
            "base_cost": "$74/month",
            "features": [
                "GKE Autopilot mode (Google manages node pools)",
                "Private cluster with private nodes by default",
                "Workload Identity for secure pod-to-GCP-service auth",
                "REGULAR release channel for stable updates",
                "Dedicated service account with least-privilege roles",
                "Master authorized networks support",
                "VPC-native cluster with IP allocation policy",
                "Deletion protection disabled for easy teardown",
            ],
            "tags": ["gcp", "gke", "kubernetes", "autopilot", "nonprod", "container"],
            "deployment_time": "10-15 minutes",
            "complexity": "intermediate",
            "use_cases": [
                "Development Kubernetes environments",
                "Microservice application testing",
                "CI/CD pipeline targets",
                "Container workload prototyping",
                "Kubernetes training and learning",
            ],
            "pillars": [
                {
                    "title": "Operational Excellence",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Fully managed cluster with automated node management and release channels",
                    "practices": [
                        "Autopilot mode eliminates node pool management overhead",
                        "REGULAR release channel provides stable automatic upgrades",
                        "Infrastructure as Code with Pulumi for repeatable deployments",
                        "Dedicated service account with clearly scoped IAM roles",
                        "Kubeconfig command exported for immediate cluster access",
                    ],
                },
                {
                    "title": "Security",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Private nodes with Workload Identity and least-privilege service account",
                    "practices": [
                        "Private nodes have no public IP addresses",
                        "Workload Identity replaces service account key distribution",
                        "Master authorized networks restrict API server access",
                        "Dedicated service account with minimum required roles",
                        "VPC-native networking for network policy support",
                    ],
                },
                {
                    "title": "Reliability",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Regional Autopilot cluster with Google-managed node health",
                    "practices": [
                        "Autopilot automatically repairs and replaces unhealthy nodes",
                        "Regional cluster distributes control plane across zones",
                        "Release channel ensures timely security patches",
                        "Google SLA-backed control plane availability",
                    ],
                },
                {
                    "title": "Performance Efficiency",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Autopilot right-sizes nodes to match workload requests",
                    "practices": [
                        "Autopilot provisions exact resources workloads request",
                        "No idle node capacity to waste compute",
                        "VPC-native networking for optimal pod-to-pod communication",
                        "Regional deployment for low-latency access across zones",
                    ],
                },
                {
                    "title": "Cost Optimization",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Pay only for running pods with no idle node costs",
                    "practices": [
                        "Autopilot charges per-pod, not per-node — no idle waste",
                        "Scales to near-zero when no workloads are running",
                        "No node pool sizing decisions to over-provision",
                        "Deletion protection disabled for easy dev environment teardown",
                    ],
                },
                {
                    "title": "Sustainability",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Autopilot eliminates wasted compute by matching resources to demand",
                    "practices": [
                        "No idle nodes consuming power when workloads are light",
                        "Bin-packing optimization reduces total compute footprint",
                        "Google Cloud carbon-neutral infrastructure",
                        "Right-sized resource allocation per workload",
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
                    "description": "Region for the GKE cluster",
                    "enum": ["us-central1", "us-east1", "us-west1", "europe-west1", "asia-east1"],
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
                "cluster_name": {
                    "type": "string",
                    "default": "",
                    "title": "Cluster Name",
                    "description": "Custom cluster name (defaults to project-env-gke)",
                    "order": 10,
                    "group": "Cluster Configuration",
                },
                "network": {
                    "type": "string",
                    "default": "default",
                    "title": "VPC Network",
                    "description": "VPC network for the cluster",
                    "order": 11,
                    "group": "Cluster Configuration",
                },
                "subnetwork": {
                    "type": "string",
                    "default": "default",
                    "title": "Subnetwork",
                    "description": "VPC subnetwork for cluster nodes",
                    "order": 12,
                    "group": "Cluster Configuration",
                },
                "release_channel": {
                    "type": "string",
                    "default": "REGULAR",
                    "title": "Release Channel",
                    "description": "GKE release channel for automatic upgrades",
                    "enum": ["RAPID", "REGULAR", "STABLE"],
                    "order": 13,
                    "group": "Cluster Configuration",
                },
                "enable_private_nodes": {
                    "type": "boolean",
                    "default": True,
                    "title": "Private Nodes",
                    "description": "Cluster nodes have no public IP addresses",
                    "order": 20,
                    "group": "Security & Access",
                },
                "enable_private_endpoint": {
                    "type": "boolean",
                    "default": False,
                    "title": "Private Endpoint",
                    "description": "Kubernetes API server accessible only via private IP (requires VPN or Cloud Interconnect)",
                    "order": 21,
                    "group": "Security & Access",
                    "conditional": {"field": "enable_private_nodes"},
                },
                "master_ipv4_cidr": {
                    "type": "string",
                    "default": "172.16.0.0/28",
                    "title": "Master CIDR",
                    "description": "CIDR range for the GKE master (must be /28)",
                    "order": 22,
                    "group": "Security & Access",
                    "conditional": {"field": "enable_private_nodes"},
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
            "required": ["project_name", "region"],
        }
