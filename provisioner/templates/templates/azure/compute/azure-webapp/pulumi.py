import pulumi
import pulumi_azure_native as azure_native
from provisioner.templates.base import InfrastructureTemplate, template_registry
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory

@template_registry("azure-webapp")
class AzureWebAppTemplate(InfrastructureTemplate):
    def __init__(self, name=None, config=None, **kwargs):
        raw_config = config or kwargs or {}
        if name is None:
            name = raw_config.get('app_name', 'mywebapp')
        super().__init__(name, raw_config)

    def create_infrastructure(self):
        params = self.config.get('parameters', {})
        def cfg(key, default=None):
            return self.config.get(key) or params.get(key) or default

        app_name = cfg('app_name', 'mywebapp')
        location = cfg('location', 'eastus')

        tags = {
            'Project': app_name,
            'Environment': 'dev',
            'ManagedBy': 'Archie'
        }

        self.resource_group = factory.create('azure-native:resources:ResourceGroup', f'rg-{app_name}',
            resource_group_name=f'rg-{app_name}',
            location=location,
            tags=tags
        )

        self.service_plan = factory.create('azure-native:web:AppServicePlan', f'plan-{app_name}',
            resource_group_name=self.resource_group.name,
            location=location,
            sku_name='B1',
            os_type='Linux',
            tags=tags
        )

        self.web_app = factory.create('azure-native:web:WebApp', app_name,
            resource_group_name=self.resource_group.name,
            location=location,
            server_farm_id=self.service_plan.id,
            site_config=azure_native.web.SiteConfigArgs(
                linux_fx_version='NODE|18-lts',
                https_only=True
            ),
            tags=tags
        )

        pulumi.export('webapp_url', self.web_app.default_hostname)
        pulumi.export('resource_group', self.resource_group.name)

        return self.get_outputs()

    def get_outputs(self):
        return {
            'webapp_url': self.web_app.default_hostname if hasattr(self, 'web_app') else None,
            'resource_group': self.resource_group.name if hasattr(self, 'resource_group') else None
        }

    @classmethod
    def get_metadata(cls):
        return {
            'name': 'azure-webapp',
            'title': 'Web Application Deployment',
            'description': 'Deploy a simple Linux Web App on Azure App Service',
            'category': 'compute',
            'cloud': 'azure',
            'tier': 'standard',
            'estimated_cost': '$10-20/mo',
            'deployment_time': '~5 min',
            'features': ['web hosting', 'linux container', 'scalable'],
            'use_cases': ['web application', 'nodejs hosting'],
            'pillars': ['performance', 'security'],
            'resources': [
                {"name": "Resource Group", "type": "azure-native:resources:ResourceGroup", "category": "management", "description": "Container for Azure resources"},
                {"name": "App Service Plan", "type": "azure-native:web:AppServicePlan", "category": "compute", "description": "Defines compute resources for web app"},
                {"name": "Web App", "type": "azure-native:web:WebApp", "category": "compute", "description": "Hosting environment for web application"}
            ],
            'config_fields': [
                {"name": "app_name", "type": "text", "label": "Application Name", "required": true, "default": "mywebapp", "group": "General", "helpText": "Name of the web application"},
                {"name": "location", "type": "select", "label": "Azure Region", "required": true, "default": "eastus", "group": "General", "helpText": "Azure region for deployment", "options": ["eastus", "westus", "eastus2", "westeurope"]}
            ]
        }
