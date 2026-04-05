"""
Azure Container App — Container App + Environment + ACR + Log Analytics

Serverless container hosting with auto-scaling. Container App Environment
with managed Log Analytics, Azure Container Registry, and HTTPS ingress.

Base cost (~$0-20/mo — consumption pricing):
- Container App Environment (consumption tier)
- Log Analytics Workspace
- Container Registry (Basic)
- Container App with HTTPS ingress
"""

from typing import Any, Dict
import pulumi

from provisioner.templates.base import InfrastructureTemplate, template_registry
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory


@template_registry("azure-containerapp-nonprod")
class AzureContainerAppNonProdTemplate(InfrastructureTemplate):

    def __init__(self, name=None, config=None, **kwargs):
        raw_config = config or kwargs or {}
        if name is None:
            name = raw_config.get('project_name', 'azure-containerapp')
        super().__init__(name, raw_config)

    def create_infrastructure(self):
        params = self.config.get('parameters', {})
        def cfg(key, default=None):
            return self.config.get(key) or params.get(key) or default

        project = cfg('project_name', 'myapp')
        env = cfg('environment', 'dev')
        location = cfg('location', 'eastus')
        team_name = cfg('team_name', '')
        container_image = cfg('container_image', 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest')
        target_port = int(cfg('target_port', '80'))
        min_replicas = int(cfg('min_replicas', '0'))
        max_replicas = int(cfg('max_replicas', '3'))
        cpu = cfg('cpu', '0.25')
        memory = cfg('memory', '0.5Gi')

        tags = {
            'Project': project, 'Environment': env,
            'ManagedBy': 'Archie', 'Team': team_name or 'unassigned',
        }

        rg_name = cfg('resource_group_name') or f'rg-{project}-{env}'
        acr_name = cfg('acr_name') or f'acr{project}{env}'.replace('-', '')[:50]
        law_name = cfg('log_analytics_name') or f'law-{project}-{env}'
        cae_name = cfg('container_env_name') or f'cae-{project}-{env}'
        ca_name = cfg('container_app_name') or f'ca-{project}-{env}'

        # 1. Resource Group (brownfield: use existing if provided)
        existing_rg = cfg('existing_resource_group', '')

        if existing_rg:
            import pulumi_azure_native as azure_native
            self.rg = azure_native.resources.ResourceGroup.get(
                'existing-rg', id=f'/subscriptions/{cfg("azure_subscription_id", "")}/resourceGroups/{existing_rg}')
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
        pulumi.export('team_name', team_name)
        pulumi.export('deployment_mode', 'brownfield' if existing_rg else 'greenfield')

        return self.get_outputs()

    def get_outputs(self):
        return {
            'resource_group_name': self.rg.name if hasattr(self, 'rg') else None,
            'acr_login_server': self.acr.login_server if hasattr(self, 'acr') else None,
            'container_app_id': self.ca.id if hasattr(self, 'ca') else None,
        }

    @classmethod
    def get_metadata(cls):
        return {
            'name': 'azure-containerapp-nonprod',
            'title': 'Container App',
            'description': 'Serverless container hosting with auto-scaling, HTTPS ingress, Container Registry, and Log Analytics. Consumption pricing for dev/staging.',
            'category': 'container',
            'cloud': 'azure',
            'tier': 'standard',
            'environment': 'nonprod',
            'estimated_cost': '$0-20/month',
            'deployment_time': '5-8 minutes',
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
            'config_fields': [
                {'key': 'project_name', 'label': 'Project Name', 'type': 'text', 'default': 'myapp', 'required': True, 'group': 'Basic'},
                {'key': 'environment', 'label': 'Environment', 'type': 'select', 'default': 'dev', 'options': ['dev', 'staging'], 'required': True, 'group': 'Basic'},
                {'key': 'location', 'label': 'Azure Region', 'type': 'text', 'default': 'eastus', 'required': True, 'group': 'Basic'},
                {'key': 'team_name', 'label': 'Team Name', 'type': 'text', 'default': '', 'group': 'Basic'},
                {'key': 'container_image', 'label': 'Container Image', 'type': 'text', 'default': 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest', 'group': 'Basic'},
                {'key': 'target_port', 'label': 'Target Port', 'type': 'number', 'default': '80', 'group': 'Basic'},
                {'key': 'cpu', 'label': 'CPU (cores)', 'type': 'text', 'default': '0.25', 'group': 'Basic'},
                {'key': 'memory', 'label': 'Memory', 'type': 'text', 'default': '0.5Gi', 'group': 'Basic'},
                {'key': 'min_replicas', 'label': 'Min Replicas', 'type': 'number', 'default': '0', 'group': 'Basic'},
                {'key': 'max_replicas', 'label': 'Max Replicas', 'type': 'number', 'default': '3', 'group': 'Basic'},
                {'key': 'existing_resource_group', 'label': 'Existing Resource Group', 'type': 'text', 'default': '', 'group': 'Existing Infrastructure',
                 'description': 'Name of an existing resource group to deploy into. Leave empty to create a new one.'},
                {'key': 'azure_subscription_id', 'label': 'Azure Subscription ID', 'type': 'text', 'default': '', 'group': 'Existing Infrastructure',
                 'description': 'Required when using an existing resource group.'},
            ],
        }
