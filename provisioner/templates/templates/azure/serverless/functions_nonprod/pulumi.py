"""
Azure Functions Stack — Function App + Storage Account + App Insights

Serverless compute for event-driven workloads. Consumption plan with
managed identity, Application Insights, and secure Storage Account.

Base cost (~$0-5/mo — consumption pricing):
- Function App (Consumption plan)
- Storage Account (required by Functions runtime)
- Application Insights
- User-Assigned Managed Identity
"""

from typing import Any, Dict
import pulumi

from provisioner.templates.base import InfrastructureTemplate, template_registry
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory


@template_registry("azure-functions-nonprod")
class AzureFunctionsNonProdTemplate(InfrastructureTemplate):

    def __init__(self, name=None, config=None, **kwargs):
        raw_config = config or kwargs or {}
        if name is None:
            name = raw_config.get('project_name', 'azure-functions')
        super().__init__(name, raw_config)

    def create_infrastructure(self):
        params = self.config.get('parameters', {})
        def cfg(key, default=None):
            return self.config.get(key) or params.get(key) or default

        project = cfg('project_name', 'myapp')
        env = cfg('environment', 'dev')
        location = cfg('location', 'eastus')
        team_name = cfg('team_name', '')
        runtime = cfg('runtime', 'node')
        runtime_version = cfg('runtime_version', '18')

        tags = {
            'Project': project, 'Environment': env,
            'ManagedBy': 'Archie', 'Team': team_name or 'unassigned',
        }

        rg_name = cfg('resource_group_name') or f'rg-{project}-{env}'
        storage_name = cfg('storage_account_name') or f'st{project}{env}'.replace('-', '')[:24]
        plan_name = cfg('app_service_plan_name') or f'plan-{project}-{env}'
        func_name = cfg('function_app_name') or f'func-{project}-{env}'
        insights_name = cfg('app_insights_name') or f'ai-{project}-{env}'
        identity_name = cfg('identity_name') or f'id-{project}-{env}'

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

        # 2. Storage Account (required by Functions)
        self.storage = factory.create('azure-native:storage:StorageAccount', storage_name,
            account_name=storage_name,
            resource_group_name=self.rg.name, location=location,
            sku={'name': 'Standard_LRS'},
            kind='StorageV2',
            minimum_tls_version='TLS1_2',
            allow_blob_public_access=False,
            tags=tags)

        # 3. App Insights
        self.insights = factory.create('azure-native:insights:Component', insights_name,
            resource_name_=insights_name,
            resource_group_name=self.rg.name, location=location,
            kind='web', application_type='web', tags=tags)

        # 4. Managed Identity
        self.identity = factory.create('azure-native:managedidentity:UserAssignedIdentity', identity_name,
            resource_name_=identity_name,
            resource_group_name=self.rg.name, location=location, tags=tags)

        # 5. Consumption Plan
        self.plan = factory.create('azure-native:web:AppServicePlan', plan_name,
            name=plan_name,
            resource_group_name=self.rg.name, location=location,
            kind='FunctionApp', reserved=True,
            sku={'name': 'Y1', 'tier': 'Dynamic'},
            tags=tags)

        # 6. Function App
        runtime_map = {'node': 'node', 'python': 'python', 'dotnet': 'dotnet-isolated'}
        worker_runtime = runtime_map.get(runtime, 'node')

        self.func = factory.create('azure-native:web:WebApp', func_name,
            name=func_name,
            resource_group_name=self.rg.name, location=location,
            server_farm_id=self.plan.id,
            kind='functionapp,linux',
            https_only=True,
            identity={'type': 'UserAssigned', 'user_assigned_identities': [self.identity.id]},
            site_config={
                'linux_fx_version': '',
                'app_settings': [
                    {'name': 'FUNCTIONS_EXTENSION_VERSION', 'value': '~4'},
                    {'name': 'FUNCTIONS_WORKER_RUNTIME', 'value': worker_runtime},
                    {'name': 'WEBSITE_RUN_FROM_PACKAGE', 'value': '1'},
                    {'name': 'AzureWebJobsStorage', 'value': pulumi.Output.concat(
                        'DefaultEndpointsProtocol=https;AccountName=', storage_name,
                        ';AccountKey=', self.storage.primary_key if hasattr(self.storage, 'primary_key') else '',
                        ';EndpointSuffix=core.windows.net')},
                    {'name': 'APPINSIGHTS_INSTRUMENTATIONKEY', 'value': self.insights.instrumentation_key},
                ],
            },
            tags=tags)

        # Exports
        pulumi.export('resource_group_name', rg_name)
        pulumi.export('function_app_name', func_name)
        pulumi.export('function_app_url', pulumi.Output.concat('https://', func_name, '.azurewebsites.net'))
        pulumi.export('storage_account_name', storage_name)
        pulumi.export('app_insights_key', self.insights.instrumentation_key)
        pulumi.export('identity_id', self.identity.id)
        pulumi.export('team_name', team_name)
        pulumi.export('deployment_mode', 'brownfield' if existing_rg else 'greenfield')

        return self.get_outputs()

    def get_outputs(self):
        return {
            'resource_group_name': self.rg.name if hasattr(self, 'rg') else None,
            'function_app_id': self.func.id if hasattr(self, 'func') else None,
            'storage_account_id': self.storage.id if hasattr(self, 'storage') else None,
        }

    @classmethod
    def get_metadata(cls):
        return {
            'name': 'azure-functions-nonprod',
            'title': 'Functions Stack',
            'description': 'Serverless compute with consumption pricing. Function App + Storage Account + Application Insights + managed identity.',
            'category': 'serverless',
            'cloud': 'azure',
            'tier': 'standard',
            'environment': 'nonprod',
            'estimated_cost': '$0-5/month',
            'deployment_time': '3-5 minutes',
            'features': [
                'Function App on Consumption plan (pay per execution)',
                'Storage Account with TLS 1.2 and no public blob access',
                'Application Insights for monitoring and telemetry',
                'User-Assigned Managed Identity for secure access',
                'Support for Node.js, Python, and .NET runtimes',
                'HTTPS-only enforcement',
                'Deploy into existing resource group (brownfield)',
            ],
            'tags': ['azure', 'serverless', 'functions', 'nonprod'],
        }
