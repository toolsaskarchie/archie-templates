"""
Azure Container App -- Container App + Environment + ACR + Log Analytics

Serverless container hosting with auto-scaling. Container App Environment
with managed Log Analytics, Azure Container Registry, and HTTPS ingress.

Base cost (~$0-20/mo -- consumption pricing):
- Container App Environment (consumption tier)
- Log Analytics Workspace
- Container Registry (Basic)
- Container App with HTTPS ingress
"""

from typing import Any, Dict, Optional
import pulumi

from provisioner.templates.base import InfrastructureTemplate, template_registry
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory


@template_registry("azure-containerapp-nonprod")
class AzureContainerAppNonProdTemplate(InfrastructureTemplate):

    def __init__(self, name: str = None, config: Dict[str, Any] = None, azure_config: Dict[str, Any] = None, **kwargs):
        raw_config = config or azure_config or kwargs or {}
        if name is None:
            name = (
                raw_config.get('project_name') or
                raw_config.get('projectName') or
                raw_config.get('parameters', {}).get('azure', {}).get('project_name') or
                'azure-containerapp'
            )
        super().__init__(name, raw_config)
        self.config = raw_config

        # Resource references (populated in create())
        self.rg: Optional[object] = None
        self.law: Optional[object] = None
        self.acr: Optional[object] = None
        self.cae: Optional[object] = None
        self.ca: Optional[object] = None

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
        """Deploy Azure Container App infrastructure (implements abstract method)"""
        return self.create()

    def create(self) -> Dict[str, Any]:
        """Deploy complete Azure Container App infrastructure"""
        project = self._cfg('project_name', 'myapp')
        env = self._cfg('environment', 'dev')
        location = self._cfg('location', 'eastus')
        team_name = self._cfg('team_name', '')
        container_image = self._cfg('container_image', 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest')
        target_port = int(self._cfg('target_port', '80'))
        min_replicas = int(self._cfg('min_replicas', '0'))
        max_replicas = int(self._cfg('max_replicas', '3'))
        cpu = self._cfg('cpu', '0.25')
        memory = self._cfg('memory', '0.5Gi')

        tags = {
            'Project': project, 'Environment': env,
            'ManagedBy': 'Archie',
        }
        if team_name:
            tags['Team'] = team_name

        rg_name = self._cfg('resource_group_name') or f'rg-{project}-{env}'
        acr_name = self._cfg('acr_name') or f'acr{project}{env}'.replace('-', '')[:50]
        law_name = self._cfg('log_analytics_name') or f'law-{project}-{env}'
        cae_name = self._cfg('container_env_name') or f'cae-{project}-{env}'
        ca_name = self._cfg('container_app_name') or f'ca-{project}-{env}'

        # 1. Resource Group (brownfield: use existing if provided)
        existing_rg = self._cfg('existing_resource_group', '')

        if existing_rg:
            import pulumi_azure_native as azure_native
            self.rg = azure_native.resources.ResourceGroup.get(
                'existing-rg', id=f'/subscriptions/{self._cfg("azure_subscription_id", "")}/resourceGroups/{existing_rg}')
            rg_name = existing_rg
        else:
            self.rg = factory.create('azure-native:resources:ResourceGroup', rg_name,
                resource_group_name=rg_name, location=location, tags=tags)

        # 2. Log Analytics Workspace
        self.law = factory.create('azure-native:operationalinsights:Workspace', law_name,
            workspace_name=law_name,
            resource_group_name=self.rg.name, location=location,
            sku={'name': 'PerGB2018'},
            retention_in_days=30, tags=tags)

        # 3. Container Registry
        self.acr = factory.create('azure-native:containerregistry:Registry', acr_name,
            registry_name=acr_name,
            resource_group_name=self.rg.name, location=location,
            sku={'name': 'Basic'}, admin_user_enabled=True, tags=tags)

        # 4. Container App Environment
        self.cae = factory.create('azure-native:app:ManagedEnvironment', cae_name,
            environment_name=cae_name,
            resource_group_name=self.rg.name, location=location,
            app_logs_configuration={
                'destination': 'log-analytics',
                'log_analytics_configuration': {
                    'customer_id': self.law.customer_id,
                    'shared_key': self.law.primary_shared_key if hasattr(self.law, 'primary_shared_key') else '',
                },
            }, tags=tags)

        # 5. Container App
        self.ca = factory.create('azure-native:app:ContainerApp', ca_name,
            container_app_name=ca_name,
            resource_group_name=self.rg.name, location=location,
            managed_environment_id=self.cae.id,
            configuration={
                'ingress': {
                    'external': True,
                    'target_port': target_port,
                    'transport': 'auto',
                },
            },
            template={
                'containers': [{
                    'name': project,
                    'image': container_image,
                    'resources': {'cpu': float(cpu), 'memory': memory},
                }],
                'scale': {
                    'min_replicas': min_replicas,
                    'max_replicas': max_replicas,
                },
            }, tags=tags)

        # Exports
        pulumi.export('resource_group_name', rg_name)
        pulumi.export('acr_login_server', self.acr.login_server)
        pulumi.export('acr_name', acr_name)
        pulumi.export('container_env_name', cae_name)
        pulumi.export('container_app_name', ca_name)
        pulumi.export('container_app_url', self.ca.latest_revision_fqdn if hasattr(self.ca, 'latest_revision_fqdn') else None)
        pulumi.export('log_analytics_name', law_name)
        pulumi.export('environment', env)
        pulumi.export('deployment_mode', 'brownfield' if existing_rg else 'greenfield')

        return self.get_outputs()

    def get_outputs(self) -> Dict[str, Any]:
        return {
            'resource_group_name': self.rg.name if self.rg else None,
            'acr_login_server': self.acr.login_server if self.acr else None,
            'acr_name': self.acr.name if self.acr else None,
            'container_env_id': self.cae.id if self.cae else None,
            'container_app_id': self.ca.id if self.ca else None,
            'container_app_url': self.ca.latest_revision_fqdn if self.ca and hasattr(self.ca, 'latest_revision_fqdn') else None,
            'log_analytics_id': self.law.id if self.law else None,
        }

    @classmethod
    def get_metadata(cls) -> Dict[str, Any]:
        return {
            'name': 'azure-containerapp-nonprod',
            'title': 'Container App',
            'description': 'Serverless container hosting with auto-scaling, HTTPS ingress, Container Registry, and Log Analytics. Consumption pricing for dev/staging.',
            'category': 'container',
            'version': '1.0.0',
            'author': 'Archie',
            'cloud': 'azure',
            'environment': 'nonprod',
            'base_cost': '$0-20/month',
            'deployment_time': '5-8 minutes',
            'complexity': 'intermediate',
            'features': [
                'Container App with HTTPS ingress and auto-scaling',
                'Container App Environment with consumption pricing',
                'Azure Container Registry (Basic tier)',
                'Log Analytics Workspace for centralized logging',
                'Configurable CPU/memory and replica count',
                'Standard tagging and naming conventions',
                'Deploy into existing resource group (brownfield)',
            ],
            'tags': ['azure', 'container', 'containerapp', 'nonprod', 'brownfield'],
            'use_cases': [
                'Microservices hosting',
                'API backends',
                'Event-driven applications',
                'Development and staging workloads',
            ],
            'pillars': [
                {
                    'title': 'Security',
                    'score': 'good',
                    'score_color': '#10b981',
                    'description': 'HTTPS ingress, managed identity via Container App Environment',
                    'practices': [
                        'HTTPS ingress enabled by default',
                        'Container Registry with admin credentials',
                        'Managed environment isolation',
                        'No public VM surface area',
                    ],
                },
                {
                    'title': 'Operational Excellence',
                    'score': 'excellent',
                    'score_color': '#10b981',
                    'description': 'Serverless operations with centralized logging',
                    'practices': [
                        'Log Analytics Workspace for centralized logs',
                        'Auto-scaling eliminates capacity planning',
                        'Standard naming and tagging conventions',
                        'Brownfield support for existing resource groups',
                    ],
                },
                {
                    'title': 'Cost Optimization',
                    'score': 'excellent',
                    'score_color': '#10b981',
                    'description': 'Consumption pricing scales to zero when idle',
                    'practices': [
                        'Consumption tier — pay only for active use',
                        'Min replicas configurable (0 for scale to zero)',
                        'Basic ACR tier for non-prod',
                        'No VM costs — fully serverless',
                    ],
                },
                {
                    'title': 'Reliability',
                    'score': 'good',
                    'score_color': '#10b981',
                    'description': 'Auto-scaling handles load spikes, managed platform',
                    'practices': [
                        'Auto-scaling from 0 to N replicas',
                        'Azure-managed platform availability',
                        'Health probes via ingress configuration',
                    ],
                },
                {
                    'title': 'Sustainability',
                    'score': 'excellent',
                    'score_color': '#10b981',
                    'description': 'Scale-to-zero eliminates idle resource consumption',
                    'practices': [
                        'Zero replicas when idle — no wasted compute',
                        'Shared container environment',
                        'Consumption model matches actual demand',
                    ],
                },
            ],
        }

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'project_name': {
                    'type': 'string',
                    'default': 'myapp',
                    'title': 'Project Name',
                    'description': 'Used in resource naming',
                    'order': 1,
                    'group': 'Essentials',
                    'isEssential': True,
                },
                'environment': {
                    'type': 'string',
                    'default': 'dev',
                    'title': 'Environment',
                    'description': 'Deployment environment',
                    'enum': ['dev', 'staging'],
                    'order': 2,
                    'group': 'Essentials',
                    'isEssential': True,
                },
                'location': {
                    'type': 'string',
                    'default': 'eastus',
                    'title': 'Azure Region',
                    'description': 'Azure region for all resources',
                    'order': 3,
                    'group': 'Essentials',
                    'isEssential': True,
                },
                'container_image': {
                    'type': 'string',
                    'default': 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest',
                    'title': 'Container Image',
                    'description': 'Docker image to deploy',
                    'order': 10,
                    'group': 'Container',
                },
                'target_port': {
                    'type': 'number',
                    'default': 80,
                    'title': 'Target Port',
                    'description': 'Port the container listens on',
                    'order': 11,
                    'group': 'Container',
                },
                'cpu': {
                    'type': 'string',
                    'default': '0.25',
                    'title': 'CPU (cores)',
                    'description': 'CPU allocation per container instance',
                    'enum': ['0.25', '0.5', '1.0', '2.0'],
                    'order': 12,
                    'group': 'Container',
                },
                'memory': {
                    'type': 'string',
                    'default': '0.5Gi',
                    'title': 'Memory',
                    'description': 'Memory allocation per container instance',
                    'enum': ['0.5Gi', '1Gi', '2Gi', '4Gi'],
                    'order': 13,
                    'group': 'Container',
                },
                'min_replicas': {
                    'type': 'number',
                    'default': 0,
                    'title': 'Min Replicas',
                    'description': 'Minimum number of container replicas (0 for scale-to-zero)',
                    'minimum': 0,
                    'maximum': 10,
                    'order': 14,
                    'group': 'Container',
                },
                'max_replicas': {
                    'type': 'number',
                    'default': 3,
                    'title': 'Max Replicas',
                    'description': 'Maximum number of container replicas',
                    'minimum': 1,
                    'maximum': 30,
                    'order': 15,
                    'group': 'Container',
                },
                'existing_resource_group': {
                    'type': 'string',
                    'default': '',
                    'title': 'Existing Resource Group',
                    'description': 'Deploy into an existing resource group (leave empty for greenfield)',
                    'order': 30,
                    'group': 'Existing Infrastructure',
                },
                'azure_subscription_id': {
                    'type': 'string',
                    'default': '',
                    'title': 'Azure Subscription ID',
                    'description': 'Required when using an existing resource group',
                    'order': 31,
                    'group': 'Existing Infrastructure',
                    'conditional': {'field': 'existing_resource_group'},
                },
                'team_name': {
                    'type': 'string',
                    'default': '',
                    'title': 'Team Name',
                    'description': 'Team that owns this resource',
                    'order': 50,
                    'group': 'Tags',
                },
            },
            'required': ['project_name'],
        }
