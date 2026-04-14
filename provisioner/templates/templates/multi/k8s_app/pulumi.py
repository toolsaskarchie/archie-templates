"""
Multi-Cloud Kubernetes App Template

Composed template: EKS / AKS / GKE managed cluster + Deployment + Service + Ingress.
Config field `cloud` selects the managed Kubernetes service.

Base cost: ~$70-150/month (varies by cloud — control plane + node)
- Managed Kubernetes cluster (EKS / AKS / GKE)
- Application Deployment with configurable replicas
- Service for internal or external access
- Ingress for HTTP routing
"""

from typing import Any, Dict, Optional
import pulumi

from provisioner.templates.base import template_registry, InfrastructureTemplate
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory


@template_registry("multi-k8s-app")
class MultiK8sAppTemplate(InfrastructureTemplate):
    """
    Multi-Cloud Kubernetes App Template

    Creates (based on cloud selection):
    - AWS: EKS Cluster + Node Group + Deployment + Service + Ingress
    - Azure: AKS Cluster + Deployment + Service + Ingress
    - GCP: GKE Cluster + Node Pool + Deployment + Service + Ingress
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

        # Resource references
        self.cluster: Optional[object] = None
        self.node_group: Optional[object] = None
        self.deployment: Optional[object] = None
        self.service: Optional[object] = None
        self.ingress: Optional[object] = None

    def _cfg(self, key: str, default=None):
        """Read config from root or parameters (Rule #6)"""
        params = self.config.get('parameters', {})
        cloud = self.config.get('cloud') or (params.get('cloud') if isinstance(params, dict) else None) or 'aws'
        cloud_params = params.get(cloud, {}) if isinstance(params, dict) else {}
        return (
            self.config.get(key) or
            (cloud_params.get(key) if isinstance(cloud_params, dict) else None) or
            (params.get(key) if isinstance(params, dict) else None) or
            default
        )

    def create_infrastructure(self) -> Dict[str, Any]:
        """Deploy multi-cloud K8s app infrastructure (implements abstract method)"""
        return self.create()

    def create(self) -> Dict[str, Any]:
        """Deploy managed K8s cluster + app to the selected cloud"""

        # Read config
        cloud = self._cfg('cloud', 'aws')
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
        enable_ingress = self._cfg('enable_ingress', True)
        if isinstance(enable_ingress, str):
            enable_ingress = enable_ingress.lower() in ('true', '1', 'yes')

        prefix = f"{project}-{env}"

        if cloud == 'aws':
            self._create_aws(prefix, project, env, team_name, cluster_name, k8s_version, node_count, node_size, app_name, app_image, app_replicas, app_port, enable_ingress)
        elif cloud == 'azure':
            self._create_azure(prefix, project, env, team_name, cluster_name, k8s_version, node_count, node_size, app_name, app_image, app_replicas, app_port, enable_ingress)
        elif cloud == 'gcp':
            self._create_gcp(prefix, project, env, team_name, cluster_name, k8s_version, node_count, node_size, app_name, app_image, app_replicas, app_port, enable_ingress)
        else:
            raise ValueError(f"Unsupported cloud: {cloud}. Must be aws, azure, or gcp.")

        # Common exports
        pulumi.export('cloud', cloud)
        pulumi.export('project_name', project)
        pulumi.export('environment', env)
        pulumi.export('cluster_name', cluster_name)
        pulumi.export('app_name', app_name)

        return self.get_outputs()

    def _create_aws(self, prefix, project, env, team_name, cluster_name, k8s_version, node_count, node_size, app_name, app_image, app_replicas, app_port, enable_ingress):
        """Deploy AWS EKS + app"""
        tags = {"Project": project, "Environment": env, "ManagedBy": "Archie", "Template": "multi-k8s-app"}
        if team_name:
            tags["Team"] = team_name

        # EKS Cluster Role
        eks_role = factory.create(
            "aws:iam:Role",
            f"{prefix}-eks-role",
            assume_role_policy="""{
                "Version": "2012-10-17",
                "Statement": [{
                    "Effect": "Allow",
                    "Principal": {"Service": "eks.amazonaws.com"},
                    "Action": "sts:AssumeRole"
                }]
            }""",
            tags={**tags, "Name": f"{prefix}-eks-role"},
        )

        # Attach EKS policies
        for policy_arn in [
            "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy",
            "arn:aws:iam::aws:policy/AmazonEKSServicePolicy",
        ]:
            policy_name = policy_arn.split('/')[-1]
            factory.create(
                "aws:iam:RolePolicyAttachment",
                f"{prefix}-{policy_name}",
                role=eks_role.name,
                policy_arn=policy_arn,
            )

        # VPC for EKS
        vpc = factory.create(
            "aws:ec2:Vpc",
            f"{prefix}-vpc",
            cidr_block="10.0.0.0/16",
            enable_dns_support=True,
            enable_dns_hostnames=True,
            tags={**tags, "Name": f"{prefix}-vpc"},
        )

        # Subnets (2 AZs required for EKS)
        import pulumi_aws as aws_sdk
        azs = aws_sdk.get_availability_zones().names[:2]
        subnets = []
        for i, az in enumerate(azs):
            subnet = factory.create(
                "aws:ec2:Subnet",
                f"{prefix}-subnet-{i}",
                vpc_id=vpc.id,
                cidr_block=f"10.0.{i}.0/24",
                availability_zone=az,
                map_public_ip_on_launch=True,
                tags={**tags, "Name": f"{prefix}-subnet-{i}"},
            )
            subnets.append(subnet)

        # EKS Cluster
        self.cluster = factory.create(
            "aws:eks:Cluster",
            cluster_name,
            name=cluster_name,
            role_arn=eks_role.arn,
            version=k8s_version,
            vpc_config={
                "subnet_ids": [s.id for s in subnets],
                "endpoint_public_access": True,
            },
            tags={**tags, "Name": cluster_name},
        )

        # Node Group Role
        node_role = factory.create(
            "aws:iam:Role",
            f"{prefix}-node-role",
            assume_role_policy="""{
                "Version": "2012-10-17",
                "Statement": [{
                    "Effect": "Allow",
                    "Principal": {"Service": "ec2.amazonaws.com"},
                    "Action": "sts:AssumeRole"
                }]
            }""",
            tags={**tags, "Name": f"{prefix}-node-role"},
        )

        for policy_arn in [
            "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy",
            "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy",
            "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly",
        ]:
            policy_name = policy_arn.split('/')[-1]
            factory.create(
                "aws:iam:RolePolicyAttachment",
                f"{prefix}-node-{policy_name}",
                role=node_role.name,
                policy_arn=policy_arn,
            )

        # Node Group
        self.node_group = factory.create(
            "aws:eks:NodeGroup",
            f"{prefix}-nodes",
            cluster_name=self.cluster.name,
            node_group_name=f"{prefix}-nodes",
            node_role_arn=node_role.arn,
            subnet_ids=[s.id for s in subnets],
            instance_types=[node_size],
            scaling_config={
                "desired_size": node_count,
                "min_size": 1,
                "max_size": node_count * 2,
            },
            tags={**tags, "Name": f"{prefix}-nodes"},
        )

        pulumi.export('cluster_endpoint', self.cluster.endpoint)
        pulumi.export('cluster_arn', self.cluster.arn)
        pulumi.export('node_group_name', self.node_group.node_group_name)

        # K8s resources deployed after cluster is ready
        self._deploy_k8s_app(app_name, app_image, app_replicas, app_port, enable_ingress, project, env, team_name)

    def _create_azure(self, prefix, project, env, team_name, cluster_name, k8s_version, node_count, node_size, app_name, app_image, app_replicas, app_port, enable_ingress):
        """Deploy Azure AKS + app"""
        tags = {"Project": project, "Environment": env, "ManagedBy": "Archie", "Template": "multi-k8s-app"}
        if team_name:
            tags["Team"] = team_name

        location = self._cfg('region', 'eastus')
        vm_size = node_size if 'Standard' in node_size else 'Standard_B2s'

        # Resource Group
        rg = factory.create(
            "azure-native:resources:ResourceGroup",
            f"{prefix}-k8s-rg",
            resource_group_name=f"{prefix}-k8s-rg",
            location=location,
            tags=tags,
        )

        # AKS Cluster
        self.cluster = factory.create(
            "azure-native:containerservice:ManagedCluster",
            cluster_name,
            resource_name_=cluster_name,
            resource_group_name=rg.name,
            location=location,
            kubernetes_version=k8s_version,
            dns_prefix=f"{prefix}-dns",
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

        pulumi.export('cluster_fqdn', self.cluster.fqdn)
        pulumi.export('cluster_id', self.cluster.id)

        # K8s resources
        self._deploy_k8s_app(app_name, app_image, app_replicas, app_port, enable_ingress, project, env, team_name)

    def _create_gcp(self, prefix, project, env, team_name, cluster_name, k8s_version, node_count, node_size, app_name, app_image, app_replicas, app_port, enable_ingress):
        """Deploy GCP GKE + app"""
        region = self._cfg('region', 'us-central1')
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
        self.cluster = factory.create(
            "gcp:container:Cluster",
            cluster_name,
            name=cluster_name,
            location=zone,
            min_master_version=k8s_version,
            remove_default_node_pool=True,
            initial_node_count=1,
            resource_labels=labels,
        )

        # Node Pool
        self.node_group = factory.create(
            "gcp:container:NodePool",
            f"{prefix}-pool",
            name=f"{prefix}-pool",
            cluster=self.cluster.name,
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

        pulumi.export('cluster_endpoint', self.cluster.endpoint)
        pulumi.export('cluster_master_version', self.cluster.master_version)

        # K8s resources
        self._deploy_k8s_app(app_name, app_image, app_replicas, app_port, enable_ingress, project, env, team_name)

    def _deploy_k8s_app(self, app_name, app_image, app_replicas, app_port, enable_ingress, project, env, team_name):
        """Deploy K8s Deployment + Service + optional Ingress (cloud-agnostic)"""

        labels = {
            "app.kubernetes.io/managed-by": "archie",
            "app.kubernetes.io/name": app_name,
            "archie/environment": env,
            "archie/project": project,
        }
        if team_name:
            labels["archie/team"] = team_name

        namespace = self._cfg('app_namespace', 'default')

        # Deployment
        self.deployment = factory.create(
            "kubernetes:apps/v1:Deployment",
            f"{app_name}-deploy",
            metadata={
                "name": app_name,
                "namespace": namespace,
                "labels": labels,
            },
            spec={
                "replicas": app_replicas,
                "selector": {"match_labels": {"app.kubernetes.io/name": app_name}},
                "template": {
                    "metadata": {"labels": {**labels, "app.kubernetes.io/name": app_name}},
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
        self.service = factory.create(
            "kubernetes:core/v1:Service",
            f"{app_name}-svc",
            metadata={
                "name": f"{app_name}-svc",
                "namespace": namespace,
                "labels": labels,
            },
            spec={
                "type": "LoadBalancer",
                "ports": [{"port": app_port, "target_port": app_port, "protocol": "TCP"}],
                "selector": {"app.kubernetes.io/name": app_name},
            },
        )

        # Ingress (optional)
        if enable_ingress:
            ingress_host = self._cfg('ingress_host', f'{app_name}.example.com')
            self.ingress = factory.create(
                "kubernetes:networking.k8s.io/v1:Ingress",
                f"{app_name}-ingress",
                metadata={
                    "name": f"{app_name}-ingress",
                    "namespace": namespace,
                    "labels": labels,
                    "annotations": {"kubernetes.io/ingress.class": "nginx"},
                },
                spec={
                    "rules": [{
                        "host": ingress_host,
                        "http": {
                            "paths": [{
                                "path": "/",
                                "path_type": "Prefix",
                                "backend": {
                                    "service": {
                                        "name": f"{app_name}-svc",
                                        "port": {"number": app_port},
                                    },
                                },
                            }],
                        },
                    }],
                },
            )

        pulumi.export('deployment_name', app_name)
        pulumi.export('service_name', f"{app_name}-svc")

    def get_outputs(self) -> Dict[str, Any]:
        """Get template outputs"""
        cloud = self._cfg('cloud', 'aws')
        return {
            "cloud": cloud,
            "cluster_name": self._cfg('cluster_name', ''),
            "app_name": self._cfg('app_name', 'my-app'),
            "cluster_id": self.cluster.id if self.cluster else None,
            "deployment_name": self.deployment.metadata.apply(lambda m: m.name) if self.deployment else None,
            "service_name": self.service.metadata.apply(lambda m: m.name) if self.service else None,
        }

    @classmethod
    def get_metadata(cls) -> Dict[str, Any]:
        """Template metadata for catalog UI"""
        return {
            "name": "multi-k8s-app",
            "title": "Multi-Cloud Kubernetes Application",
            "description": "Deploy a managed Kubernetes cluster (EKS / AKS / GKE) with a containerized application, service, and ingress. One template, three clouds.",
            "category": "compute",
            "version": "1.0.0",
            "author": "Archie",
            "cloud": "multi",
            "environment": "nonprod",
            "base_cost": "$70-150/month",
            "features": [
                "Managed K8s cluster on EKS, AKS, or GKE",
                "Application Deployment with configurable replicas",
                "LoadBalancer Service for external access",
                "Optional Ingress for HTTP routing",
                "Node group with auto-scaling bounds",
                "Kubernetes version pinning",
            ],
            "tags": ["multi-cloud", "kubernetes", "eks", "aks", "gke", "containers"],
            "deployment_time": "10-20 minutes",
            "complexity": "advanced",
            "use_cases": [
                "Cloud-agnostic container platform",
                "Multi-cloud Kubernetes strategy",
                "Quick cluster + app bootstrap for development",
                "Standardized container infrastructure",
                "Cross-cloud application portability",
            ],
            "pillars": [
                {
                    "title": "Operational Excellence",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Unified template manages cluster and application across three clouds",
                    "practices": [
                        "Single interface for EKS, AKS, and GKE cluster provisioning",
                        "Kubernetes version pinning for consistency",
                        "Infrastructure as Code for repeatable cluster setup",
                        "Application deployment included with cluster",
                        "Labels and tags for resource organization across clouds",
                    ]
                },
                {
                    "title": "Security",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Managed control plane with IAM-based access and resource limits",
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
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Managed control plane with multi-node worker pools",
                    "practices": [
                        "Cloud-managed control plane with built-in HA",
                        "Multi-node worker pools with auto-scaling bounds",
                        "Kubernetes self-healing restarts failed containers",
                        "LoadBalancer distributes traffic across pods",
                        "Multi-replica deployments for application availability",
                    ]
                },
                {
                    "title": "Performance Efficiency",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Right-sized nodes with container resource management",
                    "practices": [
                        "Configurable node instance type per cloud",
                        "Container resource requests enable efficient scheduling",
                        "Node auto-scaling prevents under-provisioning",
                        "LoadBalancer provides optimized traffic distribution",
                    ]
                },
                {
                    "title": "Cost Optimization",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Right-sized nodes with auto-scaling to match demand",
                    "practices": [
                        "Configurable node count matches workload needs",
                        "Auto-scaling bounds prevent runaway costs",
                        "AKS control plane is free (Azure advantage)",
                        "Right-sized instances across cloud providers",
                    ]
                },
                {
                    "title": "Sustainability",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Managed infrastructure with efficient bin-packing",
                    "practices": [
                        "Container bin-packing maximizes node utilization",
                        "Auto-scaling prevents over-provisioned idle nodes",
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
                "cloud": {
                    "type": "string",
                    "default": "aws",
                    "title": "Cloud Provider",
                    "description": "Managed Kubernetes service provider",
                    "enum": ["aws", "azure", "gcp"],
                    "order": 3,
                    "group": "Essentials",
                    "isEssential": True,
                },
                "cluster_name": {
                    "type": "string",
                    "default": "",
                    "title": "Cluster Name",
                    "description": "Kubernetes cluster name (auto-generated from project + env if empty)",
                    "order": 10,
                    "group": "Cluster",
                },
                "k8s_version": {
                    "type": "string",
                    "default": "1.29",
                    "title": "Kubernetes Version",
                    "description": "Kubernetes control plane version",
                    "enum": ["1.27", "1.28", "1.29", "1.30"],
                    "order": 11,
                    "group": "Cluster",
                },
                "node_count": {
                    "type": "number",
                    "default": 2,
                    "title": "Node Count",
                    "description": "Number of worker nodes",
                    "minimum": 1,
                    "maximum": 20,
                    "order": 12,
                    "group": "Cluster",
                    "cost_impact": "~$30-70/node/month",
                },
                "node_size": {
                    "type": "string",
                    "default": "t3.medium",
                    "title": "Node Size",
                    "description": "Worker node instance type (e.g., t3.medium, Standard_B2s, e2-medium)",
                    "order": 13,
                    "group": "Cluster",
                    "cost_impact": "~$30-70/node/month",
                },
                "region": {
                    "type": "string",
                    "default": "us-east-1",
                    "title": "Region",
                    "description": "Cloud region (e.g., us-east-1, eastus, us-central1)",
                    "order": 14,
                    "group": "Cluster",
                },
                "app_name": {
                    "type": "string",
                    "default": "my-app",
                    "title": "Application Name",
                    "description": "Kubernetes Deployment and Service name",
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
                    "description": "Number of application pods",
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
                    "description": "Create an Ingress resource for HTTP routing",
                    "order": 30,
                    "group": "Architecture Decisions",
                    "cost_impact": "$0/month",
                },
                "ingress_host": {
                    "type": "string",
                    "default": "my-app.example.com",
                    "title": "Ingress Hostname",
                    "description": "DNS hostname for the Ingress rule",
                    "order": 31,
                    "group": "Architecture Decisions",
                    "conditional": {"field": "enable_ingress"},
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
            "required": ["project_name", "cloud", "app_name", "app_image"],
        }
