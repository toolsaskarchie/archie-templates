"""
Azure AKS Non-Prod Template

Cost-optimized AKS cluster for dev/staging environments.
System node pool with Azure CNI networking, managed identity,
and container insights.

Base cost (~$70-150/mo):
- AKS cluster (control plane free)
- System node pool (Standard_B2s x 1-3 nodes)
- Azure CNI networking
- System-assigned managed identity
- Optional Container Insights
- Optional Azure Policy add-on
"""

from typing import Any, Dict, Optional
from pathlib import Path
import pulumi
import pulumi_azure_native as azure_native

from provisioner.templates.base import InfrastructureTemplate, template_registry
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory
from provisioner.utils.azure.tags import get_standard_tags, get_aks_cluster_tags
from provisioner.utils.azure.naming import get_resource_group_name, get_aks_cluster_name, get_resource_name


@template_registry("azure-aks-nonprod")
class AzureAKSNonProdTemplate(InfrastructureTemplate):
    """
    Azure AKS Non-Prod Template

    Cost-optimized Kubernetes cluster for non-production environments.
    Uses Standard_B2s nodes for cost savings with Azure CNI networking.
    """

    def __init__(self, name: str = None, config: Dict[str, Any] = None, azure_config: Dict[str, Any] = None, **kwargs):
        """Initialize Azure AKS Non-Prod template"""
        raw_config = config or azure_config or kwargs or {}

        if name is None:
            name = (
                raw_config.get('project_name') or
                raw_config.get('projectName') or
                raw_config.get('parameters', {}).get('azure', {}).get('project_name') or
                'azure-aks-nonprod'
            )

        super().__init__(name, raw_config)
        self.config = raw_config

        # Resource references (populated in create())
        self.resource_group: Optional[object] = None
        self.cluster: Optional[object] = None
        self.log_analytics: Optional[object] = None

    def _cfg(self, key: str, default=None):
        """Read config from root, parameters.azure, or parameters (Rule #6)"""
        params = self.config.get('parameters', {})
        azure_params = params.get('azure', {}) if isinstance(params, dict) else {}
        return (
            self.config.get(key) or
            (azure_params.get(key) if isinstance(azure_params, dict) else None) or
            (params.get(key) if isinstance(params, dict) else None) or
            default
        )

    def create_infrastructure(self) -> Dict[str, Any]:
        """Deploy AKS infrastructure (implements abstract method)"""
        return self.create()

    def create(self) -> Dict[str, Any]:
        """Deploy complete AKS infrastructure"""

        # Read config
        project = self._cfg('project_name', 'myapp')
        env = self._cfg('environment', 'dev')
        location = self._cfg('location', 'eastus')
        team_name = self._cfg('team_name', '')
        kubernetes_version = self._cfg('kubernetes_version', '1.29')
        node_count = int(self._cfg('node_count', '2'))
        min_count = int(self._cfg('min_node_count', '1'))
        max_count = int(self._cfg('max_node_count', '3'))
        vm_size = self._cfg('vm_size', 'Standard_B2s')
        os_disk_size_gb = int(self._cfg('os_disk_size_gb', '30'))
        network_plugin = self._cfg('network_plugin', 'azure')
        dns_prefix = self._cfg('dns_prefix', f'{project}-{env}')
        service_cidr = self._cfg('service_cidr', '10.0.0.0/16')
        dns_service_ip = self._cfg('dns_service_ip', '10.0.0.10')

        enable_auto_scaling = self._cfg('enable_auto_scaling', True)
        if isinstance(enable_auto_scaling, str):
            enable_auto_scaling = enable_auto_scaling.lower() in ('true', '1', 'yes')

        enable_container_insights = self._cfg('enable_container_insights', True)
        if isinstance(enable_container_insights, str):
            enable_container_insights = enable_container_insights.lower() in ('true', '1', 'yes')

        enable_azure_policy = self._cfg('enable_azure_policy', False)
        if isinstance(enable_azure_policy, str):
            enable_azure_policy = enable_azure_policy.lower() in ('true', '1', 'yes')

        # Standard tags
        tags = get_standard_tags(project=project, environment=env)
        tags['ManagedBy'] = 'Archie'
        tags['Template'] = 'azure-aks-nonprod'
        tags.update(self._cfg('tags', {}))
        if team_name:
            tags['Team'] = team_name

        # Resource names (prefer injected on upgrade — Rule #3)
        rg_name = self._cfg('resource_group_name') or f'rg-{project}-{env}-aks'
        cluster_name = self._cfg('aks_cluster_name') or get_aks_cluster_name(project, env)
        la_workspace_name = self._cfg('log_analytics_name') or f'la-{project}-{env}-aks'

        # =================================================================
        # LAYER 1: Resource Group
        # =================================================================

        self.resource_group = factory.create(
            'azure-native:resources:ResourceGroup', rg_name,
            resource_group_name=rg_name,
            location=location,
            tags={**tags, 'Purpose': 'aks-cluster'},
        )

        # =================================================================
        # LAYER 2: Log Analytics Workspace (for Container Insights)
        # =================================================================

        addon_profiles = {}

        if enable_container_insights:
            self.log_analytics = factory.create(
                'azure-native:operationalinsights:Workspace', la_workspace_name,
                workspace_name=la_workspace_name,
                resource_group_name=self.resource_group.name,
                location=location,
                sku={'name': 'PerGB2018'},
                retention_in_days=30,
                tags=tags,
            )

            addon_profiles['omsAgent'] = {
                'enabled': True,
                'config': {
                    'logAnalyticsWorkspaceResourceID': self.log_analytics.id,
                },
            }

        # =================================================================
        # LAYER 3: Azure Policy add-on (optional)
        # =================================================================

        if enable_azure_policy:
            addon_profiles['azurePolicy'] = {
                'enabled': True,
            }

        # =================================================================
        # LAYER 4: AKS Cluster
        # =================================================================

        system_pool = {
            'name': 'system',
            'mode': 'System',
            'count': node_count,
            'vm_size': vm_size,
            'os_disk_size_gb': os_disk_size_gb,
            'os_type': 'Linux',
            'os_sku': 'Ubuntu',
            'type': 'VirtualMachineScaleSets',
            'enable_auto_scaling': enable_auto_scaling,
        }

        if enable_auto_scaling:
            system_pool['min_count'] = min_count
            system_pool['max_count'] = max_count

        network_profile = {
            'network_plugin': network_plugin,
            'service_cidr': service_cidr,
            'dns_service_ip': dns_service_ip,
            'load_balancer_sku': 'standard',
        }

        # Brownfield: inject existing VNet subnet if provided
        existing_subnet_id = self._cfg('existing_subnet_id', '')
        if existing_subnet_id:
            system_pool['vnet_subnet_id'] = existing_subnet_id

        cluster_props = {
            'resource_name_': cluster_name,
            'resource_group_name': self.resource_group.name,
            'location': location,
            'dns_prefix': dns_prefix,
            'kubernetes_version': kubernetes_version,
            'identity': {'type': 'SystemAssigned'},
            'agent_pool_profiles': [system_pool],
            'network_profile': network_profile,
            'sku': {
                'name': 'Base',
                'tier': 'Free',
            },
            'tags': tags,
        }

        if addon_profiles:
            cluster_props['addon_profiles'] = addon_profiles

        self.cluster = factory.create(
            'azure-native:containerservice:ManagedCluster', cluster_name,
            **cluster_props,
        )

        # =================================================================
        # Exports (Rule #2, #7)
        # =================================================================

        pulumi.export('resource_group_name', rg_name)
        pulumi.export('aks_cluster_name', cluster_name)
        pulumi.export('aks_cluster_id', self.cluster.id)
        pulumi.export('kubernetes_version', kubernetes_version)
        pulumi.export('node_resource_group', self.cluster.node_resource_group)
        pulumi.export('aks_fqdn', self.cluster.fqdn)
        pulumi.export('environment', env)
        if enable_container_insights and self.log_analytics:
            pulumi.export('log_analytics_workspace_id', self.log_analytics.id)
        if team_name:
            pulumi.export('team_name', team_name)

        return self.get_outputs()

    def get_outputs(self) -> Dict[str, Any]:
        """Get outputs for downstream templates"""
        return {
            'resource_group_name': self.resource_group.name if self.resource_group else None,
            'aks_cluster_name': self.cluster.name if self.cluster else None,
            'aks_cluster_id': self.cluster.id if self.cluster else None,
            'kubernetes_version': self.cluster.kubernetes_version if self.cluster else None,
            'node_resource_group': self.cluster.node_resource_group if self.cluster else None,
            'aks_fqdn': self.cluster.fqdn if self.cluster else None,
            'log_analytics_workspace_id': self.log_analytics.id if self.log_analytics else None,
        }

    @classmethod
    def get_metadata(cls) -> Dict[str, Any]:
        """Template metadata for catalog UI"""
        return {
            "name": "azure-aks-nonprod",
            "title": "AKS Kubernetes Cluster",
            "description": "Cost-optimized AKS cluster with system node pool, Azure CNI networking, managed identity, and optional Container Insights. For dev/staging workloads.",
            "category": "compute",
            "version": "1.0.0",
            "author": "Archie",
            "cloud": "azure",
            "environment": "nonprod",
            "base_cost": "$70-150/month",
            "features": [
                "AKS managed Kubernetes with free control plane",
                "System node pool with Standard_B2s (burstable) VMs",
                "Azure CNI networking for pod-level network integration",
                "System-assigned managed identity (no service principal keys)",
                "Autoscaling with configurable min/max node count",
                "Optional Container Insights with Log Analytics",
                "Optional Azure Policy add-on for cluster governance",
                "Brownfield support: deploy into existing VNet subnet",
            ],
            "tags": ["azure", "kubernetes", "aks", "container", "nonprod", "cni"],
            "deployment_time": "8-12 minutes",
            "complexity": "intermediate",
            "use_cases": [
                "Microservices development and testing",
                "Container-based application staging",
                "CI/CD pipeline target environments",
                "Developer inner-loop Kubernetes testing",
                "Pre-production validation environments",
            ],
            "pillars": [
                {
                    "title": "Security",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Managed identity, RBAC, and network isolation via Azure CNI",
                    "practices": [
                        "System-assigned managed identity eliminates credential management",
                        "Azure RBAC for Kubernetes authorization",
                        "Azure CNI provides pod-level network security group support",
                        "Optional Azure Policy add-on for OPA-based governance",
                        "Standard load balancer with DDoS protection",
                    ]
                },
                {
                    "title": "Operational Excellence",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Managed control plane with automated upgrades and monitoring",
                    "practices": [
                        "Azure-managed control plane with automatic patching",
                        "Container Insights for cluster and pod-level monitoring",
                        "Log Analytics workspace for centralized logging",
                        "Infrastructure as Code with Pulumi for repeatable deployments",
                        "Standard tagging for resource organization",
                    ]
                },
                {
                    "title": "Reliability",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Autoscaling with VMSS-backed node pools for non-production reliability",
                    "practices": [
                        "Virtual Machine Scale Sets for node pool management",
                        "Cluster autoscaler adjusts node count to workload demand",
                        "Azure-managed control plane with SLA (paid tier available)",
                        "Standard load balancer for service traffic distribution",
                    ]
                },
                {
                    "title": "Cost Optimization",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Free tier control plane with burstable VMs for cost-sensitive workloads",
                    "practices": [
                        "Free tier AKS control plane (no management fee)",
                        "Standard_B2s burstable VMs (~$30/node/month)",
                        "Autoscaling reduces node count during low demand",
                        "30GB OS disk (minimal for non-production)",
                        "Per-GB Log Analytics pricing with 30-day retention",
                    ]
                },
                {
                    "title": "Sustainability",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Autoscaling and burstable VMs minimize idle resource consumption",
                    "practices": [
                        "Cluster autoscaler scales down during off-hours",
                        "Burstable VMs use CPU credits efficiently",
                        "Minimal OS disk size reduces storage footprint",
                        "Container density maximizes compute utilization",
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
                    "default": "myapp",
                    "title": "Project Name",
                    "description": "Used in resource naming (resource group, cluster, etc.)",
                    "order": 1,
                    "group": "Essentials",
                    "isEssential": True,
                },
                "environment": {
                    "type": "string",
                    "default": "dev",
                    "title": "Environment",
                    "description": "Deployment environment",
                    "enum": ["dev", "staging", "uat"],
                    "order": 2,
                    "group": "Essentials",
                    "isEssential": True,
                },
                "location": {
                    "type": "string",
                    "default": "eastus",
                    "title": "Azure Region",
                    "description": "Azure region for all resources",
                    "enum": ["eastus", "eastus2", "westus2", "westeurope", "northeurope", "southeastasia", "australiaeast"],
                    "order": 3,
                    "group": "Essentials",
                    "isEssential": True,
                },
                "kubernetes_version": {
                    "type": "string",
                    "default": "1.29",
                    "title": "Kubernetes Version",
                    "description": "AKS Kubernetes version",
                    "enum": ["1.28", "1.29", "1.30", "1.31"],
                    "order": 10,
                    "group": "Cluster Configuration",
                },
                "vm_size": {
                    "type": "string",
                    "default": "Standard_B2s",
                    "title": "Node VM Size",
                    "description": "Azure VM size for system node pool",
                    "enum": ["Standard_B2s", "Standard_B2ms", "Standard_D2s_v5", "Standard_D4s_v5"],
                    "order": 11,
                    "group": "Cluster Configuration",
                    "cost_impact": "B2s ~$30/mo, D2s ~$70/mo per node",
                },
                "node_count": {
                    "type": "number",
                    "default": 2,
                    "title": "Initial Node Count",
                    "description": "Starting number of nodes in the system pool",
                    "order": 12,
                    "group": "Cluster Configuration",
                },
                "enable_auto_scaling": {
                    "type": "boolean",
                    "default": True,
                    "title": "Enable Autoscaling",
                    "description": "Automatically scale node count based on pod resource requests",
                    "order": 20,
                    "group": "Architecture Decisions",
                    "cost_impact": "Saves cost during low demand",
                },
                "min_node_count": {
                    "type": "number",
                    "default": 1,
                    "title": "Minimum Nodes",
                    "description": "Minimum number of nodes when autoscaling",
                    "order": 21,
                    "group": "Architecture Decisions",
                    "conditional": {"field": "enable_auto_scaling"},
                },
                "max_node_count": {
                    "type": "number",
                    "default": 3,
                    "title": "Maximum Nodes",
                    "description": "Maximum number of nodes when autoscaling",
                    "order": 22,
                    "group": "Architecture Decisions",
                    "conditional": {"field": "enable_auto_scaling"},
                },
                "os_disk_size_gb": {
                    "type": "number",
                    "default": 30,
                    "title": "OS Disk Size (GB)",
                    "description": "OS disk size per node in GB",
                    "enum": [30, 50, 100, 128],
                    "order": 13,
                    "group": "Cluster Configuration",
                },
                "network_plugin": {
                    "type": "string",
                    "default": "azure",
                    "title": "Network Plugin",
                    "description": "Kubernetes network plugin",
                    "enum": ["azure", "kubenet"],
                    "order": 30,
                    "group": "Network Configuration",
                },
                "existing_subnet_id": {
                    "type": "string",
                    "default": "",
                    "title": "Existing Subnet ID",
                    "description": "Azure resource ID of existing subnet for AKS nodes (brownfield). Leave blank for new network.",
                    "order": 31,
                    "group": "Network Configuration",
                },
                "enable_container_insights": {
                    "type": "boolean",
                    "default": True,
                    "title": "Enable Container Insights",
                    "description": "Deploy Log Analytics workspace and enable Container Insights monitoring",
                    "order": 40,
                    "group": "Architecture Decisions",
                    "cost_impact": "+$2-10/month (per-GB ingestion)",
                },
                "enable_azure_policy": {
                    "type": "boolean",
                    "default": False,
                    "title": "Enable Azure Policy",
                    "description": "Azure Policy add-on for OPA Gatekeeper-based cluster governance",
                    "order": 41,
                    "group": "Architecture Decisions",
                    "cost_impact": "+$0/month",
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
            "required": ["project_name"],
        }
