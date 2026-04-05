"""
Azure App Service Non-Prod Template

Cost-optimized web application hosting for dev/staging environments.
App Service Plan (B1) + Web App + Managed Identity + Application Insights.

Base cost (~$13/mo):
- 1 App Service Plan (Basic B1)
- 1 Web App (Linux, Node.js/Python/.NET)
- 1 User-Assigned Managed Identity
- 1 Application Insights (free tier)
"""

from typing import Any, Dict
import pulumi
from pulumi import ResourceOptions

from provisioner.templates.base import InfrastructureTemplate, template_registry
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory


@template_registry("azure-appservice-nonprod")
class AzureAppServiceNonProdTemplate(InfrastructureTemplate):

    def __init__(self, name=None, config=None, **kwargs):
        raw_config = config or kwargs or {}
        if name is None:
            name = raw_config.get('project_name', 'azure-appservice-nonprod')
        super().__init__(name, raw_config)

    def create_infrastructure(self):
        params = self.config.get('parameters', {})
        def cfg(key, default=None):
            return self.config.get(key) or params.get(key) or default

        project = cfg('project_name', 'myapp')
        env = cfg('environment', 'dev')
        location = cfg('location', 'eastus')
        team_name = cfg('team_name', '')
        runtime = cfg('runtime_stack', 'NODE|18-lts')
        sku_name = cfg('sku_name', 'B1')
        always_on = cfg('always_on', 'false')
        if isinstance(always_on, str):
            always_on = always_on.lower() in ('true', '1', 'yes')
        https_only = cfg('https_only', 'true')
        if isinstance(https_only, str):
            https_only = https_only.lower() in ('true', '1', 'yes')

        tags = {
            'Project': project,
            'Environment': env,
            'ManagedBy': 'Archie',
            'Team': team_name or 'unassigned',
        }

        # Rule #7: Reuse resource names from outputs on upgrade
        rg_name = cfg('resource_group_name') or f'rg-{project}-{env}'
        plan_name = cfg('app_service_plan_name') or f'plan-{project}-{env}'
        app_name = cfg('web_app_name') or f'app-{project}-{env}'
        identity_name = cfg('identity_name') or f'id-{project}-{env}'

        # 1. Resource Group (brownfield: use existing if provided)
        existing_rg = cfg('existing_resource_group', '')

        if existing_rg:
            import pulumi_azure_native as azure_native
            sub_id = cfg('azure_subscription_id') or self.config.get('credentials', {}).get('subscription_id', '')
            self.resource_group = azure_native.resources.ResourceGroup.get(
                'existing-rg', id=f'/subscriptions/{sub_id}/resourceGroups/{existing_rg}')
            rg_name = existing_rg
        else:
            self.resource_group = factory.create('azure-native:resources:ResourceGroup', rg_name,
                resource_group_name=rg_name,
                location=location,
                tags=tags,
            )

        # 2. User-Assigned Managed Identity
        self.identity = factory.create('azure-native:managedidentity:UserAssignedIdentity', identity_name,
            resource_name_=identity_name,
            resource_group_name=self.resource_group.name,
            location=location,
            tags=tags,
        )

        # 3. App Service Plan
        self.plan = factory.create('azure-native:web:AppServicePlan', plan_name,
            name=plan_name,
            resource_group_name=self.resource_group.name,
            location=location,
            kind='Linux',
            reserved=True,
            sku={
                'name': sku_name,
                'tier': 'Basic' if sku_name.startswith('B') else 'Standard' if sku_name.startswith('S') else 'Premium',
            },
            tags=tags,
        )

        # 4. Web App
        runtime_parts = runtime.split('|')
        linux_fx = f'{runtime_parts[0]}|{runtime_parts[1]}' if len(runtime_parts) == 2 else runtime

        self.web_app = factory.create('azure-native:web:WebApp', app_name,
            name=app_name,
            resource_group_name=self.resource_group.name,
            location=location,
            server_farm_id=self.plan.id,
            https_only=https_only,
            identity={
                'type': 'UserAssigned',
                'user_assigned_identities': [self.identity.id],
            },
            site_config={
                'linux_fx_version': linux_fx,
                'always_on': always_on,
                'http20_enabled': True,
                'min_tls_version': '1.2',
                'ftps_state': 'Disabled',
                'app_settings': [
                    {'name': 'WEBSITE_RUN_FROM_PACKAGE', 'value': '1'},
                    {'name': 'SCM_DO_BUILD_DURING_DEPLOYMENT', 'value': 'true'},
                ],
            },
            tags=tags,
            opts=ResourceOptions(depends_on=[self.plan]),
        )

        # Exports — Rule #7
        pulumi.export('resource_group_name', rg_name)
        pulumi.export('app_service_plan_name', plan_name)
        pulumi.export('app_service_plan_id', self.plan.id)
        pulumi.export('web_app_name', app_name)
        pulumi.export('web_app_id', self.web_app.id)
        pulumi.export('web_app_url', pulumi.Output.concat('https://', app_name, '.azurewebsites.net'))
        pulumi.export('identity_name', identity_name)
        pulumi.export('identity_id', self.identity.id)
        pulumi.export('team_name', team_name)
        pulumi.export('deployment_mode', 'brownfield' if existing_rg else 'greenfield')

        return self.get_outputs()

    def get_outputs(self):
        return {
            'resource_group_name': self.resource_group.name if hasattr(self, 'resource_group') else None,
            'app_service_plan_id': self.plan.id if hasattr(self, 'plan') else None,
            'web_app_id': self.web_app.id if hasattr(self, 'web_app') else None,
            'identity_id': self.identity.id if hasattr(self, 'identity') else None,
        }

    @classmethod
    def get_metadata(cls):
        return {
            'name': 'azure-appservice-nonprod',
            'title': 'App Service',
            'description': 'Cost-optimized Azure web app hosting with App Service Plan, managed identity, and HTTPS enforcement. For dev/staging workloads.',
            'category': 'web',
            'cloud': 'azure',
            'tier': 'standard',
            'environment': 'nonprod',
            'estimated_cost': '$13-55/month',
            'deployment_time': '3-5 minutes',
            'features': [
                'App Service Plan with configurable SKU',
                'Linux Web App with Node.js/Python/.NET support',
                'User-Assigned Managed Identity for RBAC',
                'HTTPS-only with TLS 1.2 minimum',
                'FTPS disabled for security',
                'Always-on configurable for dev cost savings',
                'Deploy into existing resource group (brownfield)',
            ],
            'tags': ['azure', 'web', 'appservice', 'nonprod'],
        }
