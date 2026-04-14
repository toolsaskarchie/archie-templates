"""
Multi-Cloud Kubernetes App Template

Deploy managed Kubernetes clusters across AWS, Azure, and GCP simultaneously,
then deploy K8s Deployment + Service + Ingress to ALL selected clusters.
Toggle which clouds to include — deploy to 1, 2, or all 3 at once.

Base cost: ~$70-150/month per cloud
- AWS: EKS Cluster + Node Group
- Azure: Resource Group + AKS Cluster
- GCP: GKE Cluster + Node Pool
- K8s: Deployment + Service + Ingress on every selected cluster
"""

from typing import Any, Dict, List, Optional
import pulumi
import pulumi_aws as aws_sdk
import pulumi_azure_native as azure_native
import pulumi_gcp as gcp

from provisioner.templates.base import template_registry, InfrastructureTemplate
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory


@template_registry("multi-k8s-app")
class MultiK8sAppTemplate(InfrastructureTemplate):
    """
    Multi-Cloud Kubernetes App Template

    Deploys managed K8s clusters to any combination of:
    - AWS: EKS Cluster + Node Group
    - Azure: Resource Group + AKS Cluster
    - GCP: GKE Cluster + Node Pool

    Then deploys K8s Deployment + Service + Ingress to ALL selected clusters.
    """

    def __init__(self, name: str = None, config: Dict[str, Any] = None, **kwargs):
        """Initialize Multi-Cloud K8s App template"""
        raw_config = config or kwargs or {}
        if name is None:
            name = (
                raw_config.get('project_name') or
                raw_config.get('parameters', {}).get('project_name') or
                'multi-k8s-app'
            )
        super().__init__(name, raw_config)
        self.config = raw_config

        # AWS resource references
        self.aws_cluster: Optional[object] = None
        self.aws_node_group: Optional[object] = None

        # Azure resource references
        self.azure_rg: Optional[object] = None
        self.azure_cluster: Optional[object] = None

        # GCP resource references
        self.gcp_cluster: Optional[object] = None
        self.gcp_node_pool: Optional[object] = None

        # K8s resource references (per cloud)
        self.aws_deployment: Optional[object] = None
        self.aws_service: Optional[object] = None
        self.aws_ingress: Optional[object] = None
        self.azure_deployment: Optional[object] = None
        self.azure_service: Optional[object] = None
        self.azure_ingress: Optional[object] = None
        self.gcp_deployment: Optional[object] = None
        self.gcp_service: Optional[object] = None
        self.gcp_ingress: Optional[object] = None

    def _cfg(self, key: str, default=None):
        """Read config from root or parameters (Rule #6)"""
        params = self.config.get('parameters', {})
        return (
            self.config.get(key) or
            (params.get(key) if isinstance(params, dict) else None) or
            default
        )

    def _get_bool(self, key: str, default: bool = False) -> bool:
        """Read a boolean config value, handling string/bool/Decimal"""
        val = self._cfg(key, default)
        if isinstance(val, bool):
            return val
        if isinstance(val, str):
            return val.lower() in ('true', '1', 'yes')
        return bool(val)

    def create_infrastructure(self) -> Dict[str, Any]:
        """Deploy multi-cloud K8s app infrastructure (implements abstract method)"""
        return self.create()

    def create(self) -> Dict[str, Any]:
        """Deploy managed K8s clusters + app to all selected clouds"""

        project = self._cfg('project_name', 'k8s-app')
        env = self._cfg('environment', 'dev')
        team_name = self._cfg('team_name', '')
        cluster_name = self._cfg('cluster_name', f'{project}-{env}')
        k8s_version = self._cfg('k8s_version', '1.29')
        node_count = int(self._cfg('node_count', 2))
        node_size = self._cfg('node_size', 't3.medium')
        app_name = self._cfg('app_name', 'my-app')
        app_image = self._cfg('app_image', 'nginx:latest')
        app_replicas = int(self._cfg('app_replicas', 2))
        app_port = int(self._cfg('app_port', 80))
        enable_ingress = self._get_bool('enable_ingress', True)

        deploy_aws = self._get_bool('deploy_aws', True)
        deploy_azure = self._get_bool('deploy_azure', False)
        deploy_gcp = self._get_bool('deploy_gcp', False)

        prefix = f"{project}-{env}"
        clouds_deployed: List[str] = []

        if deploy_aws:
            self._create_aws(prefix, project, env, team_name, cluster_name, k8s_version,
                             node_count, node_size)
            self._deploy_k8s_app('aws', app_name, app_image, app_replicas, app_port,
                                 enable_ingress, project, env, team_name)
            clouds_deployed.append('aws')

        if deploy_azure:
            self._create_azure(prefix, project, env, team_name, cluster_name, k8s_version,
                               node_count, node_size)
            self._deploy_k8s_app('azure', app_name, app_image, app_replicas, app_port,
                                 enable_ingress, project, env, team_name)
            clouds_deployed.append('azure')

        if deploy_gcp:
            self._create_gcp(prefix, project, env, team_name, cluster_name, k8s_version,
                             node_count, node_size)
            self._deploy_k8s_app('gcp', app_name, app_image, app_replicas, app_port,
                                 enable_ingress, project, env, team_name)
            clouds_deployed.append('gcp')

        # Common exports
        pulumi.export('clouds_deployed', clouds_deployed)
        pulumi.export('project_name', project)
        pulumi.export('environment', env)
        pulumi.export('cluster_name', cluster_name)
        pulumi.export('app_name', app_name)

        return self.get_outputs()

    def _create_aws(self, prefix, project, env, team_name, cluster_name, k8s_version,
                    node_count, node_size):
        """Deploy AWS EKS cluster + node group"""
        tags = {"Project": project, "Environment": env, "ManagedBy": "Archie", "Template": "multi-k8s-app"}
        if team_name:
            tags["Team"] = team_name

        # EKS Cluster Role
        eks_role = factory.create(
            "aws:iam:Role",
            f"aws-{prefix}-eks-role",
            assume_role_policy="""{
                "Version": "2012-10-17",
                "Statement": [{
                    "Effect": "Allow",
                    "Principal": {"Service": "eks.amazonaws.com"},
                    "Action": "sts:AssumeRole"
                }]
            }""",
            tags={**tags, "Name": f"aws-{prefix}-eks-role"},
        )

        # Attach EKS policies
        for policy_arn in [
            "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy",
            "arn:aws:iam::aws:policy/AmazonEKSServicePolicy",
        ]:
            policy_name = policy_arn.split('/')[-1]
            factory.create(
                "aws:iam:RolePolicyAttachment",
                f"aws-{prefix}-{policy_name}",
                role=eks_role.name,
                policy_arn=policy_arn,
            )

        # VPC for EKS
        vpc = factory.create(
            "aws:ec2:Vpc",
            f"aws-{prefix}-vpc",
            cidr_block="10.0.0.0/16",
            enable_dns_support=True,
            enable_dns_hostnames=True,
            tags={**tags, "Name": f"aws-{prefix}-vpc"},
        )

        # Subnets (2 AZs required for EKS)
        azs = aws_sdk.get_availability_zones().names[:2]
        subnets = []
        for i, az in enumerate(azs):
            subnet = factory.create(
                "aws:ec2:Subnet",
                f"aws-{prefix}-subnet-{i}",
                vpc_id=vpc.id,
                cidr_block=f"10.0.{i}.0/24",
                availability_zone=az,
                map_public_ip_on_launch=True,
                tags={**tags, "Name": f"aws-{prefix}-subnet-{i}"},
            )
            subnets.append(subnet)

        # EKS Cluster
        aws_cluster_name = f"aws-{cluster_name}"
        self.aws_cluster = factory.create(
            "aws:eks:Cluster",
            aws_cluster_name,
            name=aws_cluster_name,
            role_arn=eks_role.arn,
            version=k8s_version,
            vpc_config={
                "subnet_ids": [s.id for s in subnets],
                "endpoint_public_access": True,
            },
            tags={**tags, "Name": aws_cluster_name},
        )

        # Node Group Role
        node_role = factory.create(
            "aws:iam:Role",
            f"aws-{prefix}-node-role",
            assume_role_policy="""{
                "Version": "2012-10-17",
                "Statement": [{
                    "Effect": "Allow",
                    "Principal": {"Service": "ec2.amazonaws.com"},
                    "Action": "sts:AssumeRole"
                }]
            }""",
            tags={**tags, "Name": f"aws-{prefix}-node-role"},
        )

        for policy_arn in [
            "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy",
            "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy",
            "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly",
        ]:
            policy_name = policy_arn.split('/')[-1]
            factory.create(
                "aws:iam:RolePolicyAttachment",
                f"aws-{prefix}-node-{policy_name}",
                role=node_role.name,
                policy_arn=policy_arn,
            )

        # Node Group
        self.aws_node_group = factory.create(
            "aws:eks:NodeGroup",
            f"aws-{prefix}-nodes",
            cluster_name=self.aws_cluster.name,
            node_group_name=f"aws-{prefix}-nodes",
            node_role_arn=node_role.arn,
            subnet_ids=[s.id for s in subnets],
            instance_types=[node_size],
            scaling_config={
                "desired_size": node_count,
                "min_size": 1,
                "max_size": node_count * 2,
            },
            tags={**tags, "Name": f"aws-{prefix}-nodes"},
        )

        pulumi.export('aws_cluster_endpoint', self.aws_cluster.endpoint)
        pulumi.export('aws_cluster_arn', self.aws_cluster.arn)
        pulumi.export('aws_node_group_name', self.aws_node_group.node_group_name)

    def _create_azure(self, prefix, project, env, team_name, cluster_name, k8s_version,
                      node_count, node_size):
        """Deploy Azure AKS cluster"""
        tags = {"Project": project, "Environment": env, "ManagedBy": "Archie", "Template": "multi-k8s-app"}
        if team_name:
            tags["Team"] = team_name

        location = self._cfg('azure_region', 'eastus')
        vm_size = node_size if 'Standard' in node_size else 'Standard_B2s'

        # Resource Group
        self.azure_rg = factory.create(
            "azure-native:resources:ResourceGroup",
            f"azure-{prefix}-k8s-rg",
            resource_group_name=f"azure-{prefix}-k8s-rg",
            location=location,
            tags=tags,
        )

        # AKS Cluster
        azure_cluster_name = f"azure-{cluster_name}"
        self.azure_cluster = factory.create(
            "azure-native:containerservice:ManagedCluster",
            azure_cluster_name,
            resource_name_=azure_cluster_name,
            resource_group_name=self.azure_rg.name,
            location=location,
            kubernetes_version=k8s_version,
            dns_prefix=f"azure-{prefix}-dns",
            agent_pool_profiles=[{
                "name": "default",
                "count": node_count,
                "vm_size": vm_size,
                "mode": "System",
                "os_type": "Linux",
            }],
            identity={"type": "SystemAssigned"},
            tags=tags,
        )

        pulumi.export('azure_cluster_fqdn', self.azure_cluster.fqdn)
        pulumi.export('azure_cluster_id', self.azure_cluster.id)

    def _create_gcp(self, prefix, project, env, team_name, cluster_name, k8s_version,
                    node_count, node_size):
        """Deploy GCP GKE cluster + node pool"""
        region = self._cfg('gcp_region', 'us-central1')
        zone = f"{region}-a"

        labels = {
            "project": project.lower().replace(' ', '-'),
            "environment": env,
            "managed-by": "archie",
        }
        if team_name:
            labels["team"] = team_name.lower().replace(' ', '-')

        machine_type = node_size if 'e2-' in node_size or 'n2-' in node_size else 'e2-medium'

        # GKE Cluster
        gcp_cluster_name = f"gcp-{cluster_name}"
        self.gcp_cluster = factory.create(
            "gcp:container:Cluster",
            gcp_cluster_name,
            name=gcp_cluster_name,
            location=zone,
            min_master_version=k8s_version,
            remove_default_node_pool=True,
            initial_node_count=1,
            resource_labels=labels,
        )

        # Node Pool
        self.gcp_node_pool = factory.create(
            "gcp:container:NodePool",
            f"gcp-{prefix}-pool",
            name=f"gcp-{prefix}-pool",
            cluster=self.gcp_cluster.name,
            location=zone,
            node_count=node_count,
            node_config={
                "machine_type": machine_type,
                "disk_size_gb": 50,
                "oauth_scopes": [
                    "https://www.googleapis.com/auth/devstorage.read_only",
                    "https://www.googleapis.com/auth/logging.write",
                    "https://www.googleapis.com/auth/monitoring",
                ],
                "labels": labels,
            },
        )

        pulumi.export('gcp_cluster_endpoint', self.gcp_cluster.endpoint)
        pulumi.export('gcp_cluster_master_version', self.gcp_cluster.master_version)

    def _deploy_k8s_app(self, cloud: str, app_name, app_image, app_replicas, app_port,
                        enable_ingress, project, env, team_name):
        """Deploy K8s Deployment + Service + optional Ingress for a specific cloud"""

        labels = {
            "app.kubernetes.io/managed-by": "archie",
            "app.kubernetes.io/name": app_name,
            "archie/environment": env,
            "archie/project": project,
            "archie/cloud": cloud,
        }
        if team_name:
            labels["archie/team"] = team_name

        namespace = self._cfg('app_namespace', 'default')
        resource_prefix = f"{cloud}-{app_name}"

        # Deployment
        deployment = factory.create(
            "kubernetes:apps/v1:Deployment",
            f"{resource_prefix}-deploy",
            metadata={
                "name": f"{cloud}-{app_name}",
                "namespace": namespace,
                "labels": labels,
            },
            spec={
                "replicas": app_replicas,
                "selector": {"match_labels": {"app.kubernetes.io/name": app_name, "archie/cloud": cloud}},
                "template": {
                    "metadata": {"labels": {**labels, "app.kubernetes.io/name": app_name, "archie/cloud": cloud}},
                    "spec": {
                        "containers": [{
                            "name": app_name,
                            "image": app_image,
                            "ports": [{"container_port": app_port}],
                            "resources": {
                                "limits": {"cpu": "500m", "memory": "256Mi"},
                                "requests": {"cpu": "100m", "memory": "128Mi"},
                            },
                        }],
                    },
                },
            },
        )

        # Service
        service = factory.create(
            "kubernetes:core/v1:Service",
            f"{resource_prefix}-svc",
            metadata={
                "name": f"{cloud}-{app_name}-svc",
                "namespace": namespace,
                "labels": labels,
            },
            spec={
                "type": "LoadBalancer",
                "ports": [{"port": app_port, "target_port": app_port, "protocol": "TCP"}],
                "selector": {"app.kubernetes.io/name": app_name, "archie/cloud": cloud},
            },
        )

        # Ingress (optional)
        ingress = None
        if enable_ingress:
            ingress_host = self._cfg('ingress_host', f'{app_name}.example.com')
            ingress = factory.create(
                "kubernetes:networking.k8s.io/v1:Ingress",
                f"{resource_prefix}-ingress",
                metadata={
                    "name": f"{cloud}-{app_name}-ingress",
                    "namespace": namespace,
                    "labels": labels,
                    "annotations": {"kubernetes.io/ingress.class": "nginx"},
                },
                spec={
                    "rules": [{
                        "host": f"{cloud}.{ingress_host}",
                        "http": {
                            "paths": [{
                                "path": "/",
                                "path_type": "Prefix",
                                "backend": {
                                    "service": {
                                        "name": f"{cloud}-{app_name}-svc",
                                        "port": {"number": app_port},
                                    },
                                },
                            }],
                        },
                    }],
                },
            )

        pulumi.export(f'{cloud}_deployment_name', f"{cloud}-{app_name}")
        pulumi.export(f'{cloud}_service_name', f"{cloud}-{app_name}-svc")

        # Store references per cloud
        if cloud == 'aws':
            self.aws_deployment = deployment
            self.aws_service = service
            self.aws_ingress = ingress
        elif cloud == 'azure':
            self.azure_deployment = deployment
            self.azure_service = service
            self.azure_ingress = ingress
        elif cloud == 'gcp':
            self.gcp_deployment = deployment
            self.gcp_service = service
            self.gcp_ingress = ingress

    def get_outputs(self) -> Dict[str, Any]:
        """Get template outputs for all deployed clouds"""
        outputs: Dict[str, Any] = {
            "project_name": self._cfg('project_name', 'k8s-app'),
            "environment": self._cfg('environment', 'dev'),
            "cluster_name": self._cfg('cluster_name', ''),
            "app_name": self._cfg('app_name', 'my-app'),
        }

        # AWS outputs
        if self.aws_cluster:
            outputs["aws_cluster_endpoint"] = self.aws_cluster.endpoint
            outputs["aws_cluster_arn"] = self.aws_cluster.arn
            outputs["aws_node_group_name"] = self.aws_node_group.node_group_name if self.aws_node_group else None
            outputs["aws_deployment_name"] = self.aws_deployment.metadata.apply(lambda m: m.name) if self.aws_deployment else None
            outputs["aws_service_name"] = self.aws_service.metadata.apply(lambda m: m.name) if self.aws_service else None

        # Azure outputs
        if self.azure_cluster:
            outputs["azure_cluster_fqdn"] = self.azure_cluster.fqdn
            outputs["azure_cluster_id"] = self.azure_cluster.id
            outputs["azure_deployment_name"] = self.azure_deployment.metadata.apply(lambda m: m.name) if self.azure_deployment else None
            outputs["azure_service_name"] = self.azure_service.metadata.apply(lambda m: m.name) if self.azure_service else None

        # GCP outputs
        if self.gcp_cluster:
            outputs["gcp_cluster_endpoint"] = self.gcp_cluster.endpoint
            outputs["gcp_cluster_master_version"] = self.gcp_cluster.master_version
            outputs["gcp_deployment_name"] = self.gcp_deployment.metadata.apply(lambda m: m.name) if self.gcp_deployment else None
            outputs["gcp_service_name"] = self.gcp_service.metadata.apply(lambda m: m.name) if self.gcp_service else None

        return outputs

    @classmethod
    def get_metadata(cls) -> Dict[str, Any]:
        """Template metadata for catalog UI"""
        return {
            "name": "multi-k8s-app",
            "title": "Multi-Cloud Kubernetes Application",
            "description": "Deploy managed Kubernetes clusters across AWS, Azure, and GCP simultaneously, then deploy your application to all selected clusters. Toggle which clouds to include.",
            "category": "compute",
            "version": "2.0.0",
            "author": "Archie",
            "cloud": "multi",
            "environment": "nonprod",
            "base_cost": "$70-150/month per cloud",
            "features": [
                "Deploy to 1, 2, or all 3 clouds simultaneously",
                "AWS: EKS Cluster + Node Group with IAM roles",
                "Azure: AKS Cluster with managed identity",
                "GCP: GKE Cluster + Node Pool with OAuth scopes",
                "K8s Deployment + Service + Ingress on every selected cluster",
                "Cross-cloud Kubernetes with unified governance",
                "Single deploy creates identical app across clouds",
            ],
            "tags": ["multi-cloud", "kubernetes", "eks", "aks", "gke", "containers", "cross-cloud"],
            "deployment_time": "10-25 minutes",
            "complexity": "advanced",
            "use_cases": [
                "Multi-cloud Kubernetes redundancy",
                "Disaster recovery across cloud providers",
                "Cloud migration with parallel clusters",
                "Vendor lock-in avoidance for container platform",
                "Cross-cloud application portability testing",
            ],
            "pillars": [
                {
                    "title": "Operational Excellence",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Single template deploys clusters and applications across three clouds simultaneously",
                    "practices": [
                        "One deploy creates K8s clusters on multiple clouds at once",
                        "Identical application deployment across all selected clusters",
                        "Kubernetes version pinning for consistency across clouds",
                        "Infrastructure as Code for repeatable multi-cloud K8s setup",
                        "Labels and tags for resource organization across clouds",
                    ]
                },
                {
                    "title": "Security",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Managed control planes with IAM-based access and resource limits",
                    "practices": [
                        "Cloud-managed control plane security patches",
                        "IAM roles (AWS) / Managed Identity (Azure) / OAuth scopes (GCP)",
                        "Container resource limits prevent resource exhaustion",
                        "VPC-based network isolation for cluster nodes",
                        "Kubernetes RBAC available for application-level security",
                    ]
                },
                {
                    "title": "Reliability",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Cross-cloud Kubernetes provides ultimate application redundancy",
                    "practices": [
                        "Application runs on clusters across multiple clouds",
                        "No single cloud is a single point of failure",
                        "Cloud-managed control plane with built-in HA per cluster",
                        "Kubernetes self-healing restarts failed containers",
                        "Multi-replica deployments on every cluster",
                    ]
                },
                {
                    "title": "Performance Efficiency",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Right-sized nodes with container resource management per cloud",
                    "practices": [
                        "Configurable node instance type per cloud",
                        "Container resource requests enable efficient scheduling",
                        "Node auto-scaling prevents under-provisioning",
                        "LoadBalancer provides optimized traffic distribution per cluster",
                    ]
                },
                {
                    "title": "Cost Optimization",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Toggle clouds on/off to control Kubernetes spend",
                    "practices": [
                        "Deploy only to clouds you need (1, 2, or all 3)",
                        "Configurable node count matches workload needs",
                        "Auto-scaling bounds prevent runaway costs",
                        "AKS control plane is free (Azure advantage)",
                    ]
                },
                {
                    "title": "Sustainability",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Managed infrastructure with efficient bin-packing across clouds",
                    "practices": [
                        "Toggle off unused clouds to reduce resource consumption",
                        "Container bin-packing maximizes node utilization",
                        "Managed control plane shares cloud infrastructure",
                        "Right-sized nodes reduce energy waste",
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
                    "default": "k8s-app",
                    "title": "Project Name",
                    "description": "Project identifier used in resource naming",
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
                "deploy_aws": {
                    "type": "boolean",
                    "default": True,
                    "title": "Deploy to AWS",
                    "description": "Deploy EKS Cluster + Node Group on AWS",
                    "order": 3,
                    "group": "Cloud Selection",
                    "isEssential": True,
                },
                "deploy_azure": {
                    "type": "boolean",
                    "default": False,
                    "title": "Deploy to Azure",
                    "description": "Deploy AKS Cluster on Azure",
                    "order": 4,
                    "group": "Cloud Selection",
                    "isEssential": True,
                },
                "deploy_gcp": {
                    "type": "boolean",
                    "default": False,
                    "title": "Deploy to GCP",
                    "description": "Deploy GKE Cluster + Node Pool on GCP",
                    "order": 5,
                    "group": "Cloud Selection",
                    "isEssential": True,
                },
                "cluster_name": {
                    "type": "string",
                    "default": "",
                    "title": "Cluster Name",
                    "description": "Base cluster name (auto-prefixed with cloud name, e.g., aws-mycluster)",
                    "order": 10,
                    "group": "Cluster",
                },
                "k8s_version": {
                    "type": "string",
                    "default": "1.29",
                    "title": "Kubernetes Version",
                    "description": "Kubernetes control plane version (same across all clouds)",
                    "enum": ["1.27", "1.28", "1.29", "1.30"],
                    "order": 11,
                    "group": "Cluster",
                },
                "node_count": {
                    "type": "number",
                    "default": 2,
                    "title": "Node Count",
                    "description": "Number of worker nodes per cloud",
                    "minimum": 1,
                    "maximum": 20,
                    "order": 12,
                    "group": "Cluster",
                    "cost_impact": "~$30-70/node/month per cloud",
                },
                "node_size": {
                    "type": "string",
                    "default": "t3.medium",
                    "title": "Node Size",
                    "description": "Worker node instance type (e.g., t3.medium for AWS, Standard_B2s for Azure, e2-medium for GCP)",
                    "order": 13,
                    "group": "Cluster",
                    "cost_impact": "~$30-70/node/month",
                },
                "app_name": {
                    "type": "string",
                    "default": "my-app",
                    "title": "Application Name",
                    "description": "Kubernetes Deployment and Service name (deployed to all selected clusters)",
                    "order": 20,
                    "group": "Application",
                },
                "app_image": {
                    "type": "string",
                    "default": "nginx:latest",
                    "title": "Container Image",
                    "description": "Docker image for the application",
                    "order": 21,
                    "group": "Application",
                },
                "app_replicas": {
                    "type": "number",
                    "default": 2,
                    "title": "App Replicas",
                    "description": "Number of application pods per cluster",
                    "minimum": 1,
                    "maximum": 20,
                    "order": 22,
                    "group": "Application",
                },
                "app_port": {
                    "type": "number",
                    "default": 80,
                    "title": "App Port",
                    "description": "Container port the application listens on",
                    "order": 23,
                    "group": "Application",
                },
                "app_namespace": {
                    "type": "string",
                    "default": "default",
                    "title": "App Namespace",
                    "description": "Kubernetes namespace for the application",
                    "order": 24,
                    "group": "Application",
                },
                "enable_ingress": {
                    "type": "boolean",
                    "default": True,
                    "title": "Enable Ingress",
                    "description": "Create an Ingress resource for HTTP routing on each cluster",
                    "order": 30,
                    "group": "Architecture Decisions",
                    "cost_impact": "$0/month",
                },
                "ingress_host": {
                    "type": "string",
                    "default": "my-app.example.com",
                    "title": "Ingress Hostname",
                    "description": "DNS hostname for the Ingress rule (prefixed with cloud name, e.g., aws.my-app.example.com)",
                    "order": 31,
                    "group": "Architecture Decisions",
                    "conditional": {"field": "enable_ingress"},
                },
                "azure_region": {
                    "type": "string",
                    "default": "eastus",
                    "title": "Azure Region",
                    "description": "Azure region for AKS cluster (e.g., eastus, westus2, westeurope)",
                    "order": 40,
                    "group": "Cloud Regions",
                    "conditional": {"field": "deploy_azure"},
                },
                "gcp_region": {
                    "type": "string",
                    "default": "us-central1",
                    "title": "GCP Region",
                    "description": "GCP region for GKE cluster (e.g., us-central1, us-east1, europe-west1)",
                    "order": 41,
                    "group": "Cloud Regions",
                    "conditional": {"field": "deploy_gcp"},
                },
                "team_name": {
                    "type": "string",
                    "default": "",
                    "title": "Team Name",
                    "description": "Team that owns this cluster and application",
                    "order": 50,
                    "group": "Tags",
                },
            },
            "required": ["project_name", "app_name", "app_image"],
        }
