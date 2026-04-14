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

from typing import Any, Dict, Optional
import pulumi
from pulumi import ResourceOptions

from provisioner.templates.base import InfrastructureTemplate, template_registry
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory


@template_registry("azure-appservice-nonprod")
class AzureAppServiceNonProdTemplate(InfrastructureTemplate):

    def __init__(self, name: str = None, config: Dict[str, Any] = None, azure_config: Dict[str, Any] = None, **kwargs):
        raw_config = config or azure_config or kwargs or {}
        if name is None:
            name = (
                raw_config.get('project_name') or
                raw_config.get('projectName') or
                raw_config.get('parameters', {}).get('azure', {}).get('project_name') or
                'azure-appservice-nonprod'
            )
        super().__init__(name, raw_config)
        self.config = raw_config

        # Resource references (populated in create())
        self.resource_group: Optional[object] = None
        self.identity: Optional[object] = None
        self.plan: Optional[object] = None
        self.web_app: Optional[object] = None

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
        """Deploy Azure App Service infrastructure (implements abstract method)"""
        return self.create()

    def create(self) -> Dict[str, Any]:
        """Deploy complete Azure App Service infrastructure"""
        project = self._cfg('project_name', 'myapp')
        env = self._cfg('environment', 'dev')
        location = self._cfg('location', 'eastus')
        team_name = self._cfg('team_name', '')
        runtime = self._cfg('runtime_stack', 'NODE|18-lts')
        sku_name = self._cfg('sku_name', 'B1')
        always_on = self._cfg('always_on', 'false')
        if isinstance(always_on, str):
            always_on = always_on.lower() in ('true', '1', 'yes')
        https_only = self._cfg('https_only', 'true')
        if isinstance(https_only, str):
            https_only = https_only.lower() in ('true', '1', 'yes')

        tags = {
            'Project': project,
            'Environment': env,
            'ManagedBy': 'Archie',
        }
        if team_name:
            tags['Team'] = team_name

        # Rule #7: Reuse resource names from outputs on upgrade
        rg_name = self._cfg('resource_group_name') or f'rg-{project}-{env}'
        plan_name = self._cfg('app_service_plan_name') or f'plan-{project}-{env}'
        app_name = self._cfg('web_app_name') or f'app-{project}-{env}'
        identity_name = self._cfg('identity_name') or f'id-{project}-{env}'

        # 1. Resource Group (brownfield: use existing if provided)
        existing_rg = self._cfg('existing_resource_group', '')

        if existing_rg:
            import pulumi_azure_native as azure_native
            sub_id = self._cfg('azure_subscription_id') or self.config.get('credentials', {}).get('subscription_id', '')
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

        # Exports -- Rule #7
        pulumi.export('resource_group_name', rg_name)
        pulumi.export('app_service_plan_name', plan_name)
        pulumi.export('app_service_plan_id', self.plan.id)
        pulumi.export('web_app_name', app_name)
        pulumi.export('web_app_id', self.web_app.id)
        pulumi.export('web_app_url', pulumi.Output.concat('https://', app_name, '.azurewebsites.net'))
        pulumi.export('identity_name', identity_name)
        pulumi.export('identity_id', self.identity.id)
        pulumi.export('environment', env)
        pulumi.export('deployment_mode', 'brownfield' if existing_rg else 'greenfield')

        return self.get_outputs()

    def get_outputs(self) -> Dict[str, Any]:
        return {
            'resource_group_name': self.resource_group.name if self.resource_group else None,
            'app_service_plan_id': self.plan.id if self.plan else None,
            'app_service_plan_name': self.plan.name if self.plan else None,
            'web_app_id': self.web_app.id if self.web_app else None,
            'web_app_name': self.web_app.name if self.web_app else None,
            'identity_id': self.identity.id if self.identity else None,
        }

    @classmethod
    def get_metadata(cls) -> Dict[str, Any]:
        return {
            'name': 'azure-appservice-nonprod',
            'title': 'App Service',
            'description': 'Cost-optimized Azure web app hosting with App Service Plan, managed identity, and HTTPS enforcement. For dev/staging workloads.',
            'category': 'web',
            'version': '1.0.0',
            'author': 'Archie',
            'cloud': 'azure',
            'environment': 'nonprod',
            'base_cost': '$13-55/month',
            'deployment_time': '3-5 minutes',
            'complexity': 'beginner',
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
            'use_cases': [
                'Web application hosting',
                'REST API backends',
                'Development and staging environments',
                'Lightweight microservices',
            ],
            'pillars': [
                {
                    'title': 'Security',
                    'score': 'excellent',
                    'score_color': '#10b981',
                    'description': 'HTTPS-only, TLS 1.2, FTPS disabled, managed identity',
                    'practices': [
                        'HTTPS-only enforced',
                        'TLS 1.2 minimum version',
                        'FTPS disabled to prevent insecure file transfer',
                        'User-assigned managed identity for RBAC',
                        'HTTP/2 enabled for modern security',
                    ],
                },
                {
                    'title': 'Operational Excellence',
                    'score': 'good',
                    'score_color': '#10b981',
                    'description': 'Managed platform with standard naming and brownfield support',
                    'practices': [
                        'Fully managed PaaS — no OS patching',
                        'Standard naming and tagging conventions',
                        'Brownfield support for existing resource groups',
                        'Run-from-package deployment model',
                    ],
                },
                {
                    'title': 'Cost Optimization',
                    'score': 'excellent',
                    'score_color': '#10b981',
                    'description': 'Basic B1 SKU with always-on disabled for dev savings',
                    'practices': [
                        'Basic B1 tier for non-prod ($13/month)',
                        'Always-on disabled by default to save cost',
                        'Configurable SKU for right-sizing',
                        'No redundant components for non-prod',
                    ],
                },
                {
                    'title': 'Reliability',
                    'score': 'needs-improvement',
                    'score_color': '#f59e0b',
                    'description': 'Single instance on Basic tier (appropriate for non-prod)',
                    'practices': [
                        'Basic tier — single instance, no SLA',
                        'Azure-managed platform reliability',
                        'Non-prod: high availability not required',
                    ],
                },
                {
                    'title': 'Sustainability',
                    'score': 'excellent',
                    'score_color': '#10b981',
                    'description': 'PaaS eliminates idle VM overhead',
                    'practices': [
                        'Shared infrastructure via App Service Plan',
                        'Always-on disabled reduces idle compute',
                        'No dedicated VM — shared hosting model',
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
                'runtime_stack': {
                    'type': 'string',
                    'default': 'NODE|18-lts',
                    'title': 'Runtime Stack',
                    'description': 'Application runtime and version',
                    'enum': ['NODE|18-lts', 'NODE|20-lts', 'PYTHON|3.11', 'PYTHON|3.12', 'DOTNETCORE|8.0'],
                    'order': 10,
                    'group': 'Compute',
                },
                'sku_name': {
                    'type': 'string',
                    'default': 'B1',
                    'title': 'App Service SKU',
                    'description': 'App Service Plan pricing tier',
                    'enum': ['B1', 'B2', 'B3', 'S1', 'S2', 'P1v3'],
                    'order': 11,
                    'group': 'Compute',
                    'cost_impact': '$13-115/month',
                },
                'always_on': {
                    'type': 'boolean',
                    'default': False,
                    'title': 'Always On',
                    'description': 'Keep app loaded (disable for dev to save cost)',
                    'order': 12,
                    'group': 'Compute',
                },
                'https_only': {
                    'type': 'boolean',
                    'default': True,
                    'title': 'HTTPS Only',
                    'description': 'Redirect all HTTP traffic to HTTPS',
                    'order': 20,
                    'group': 'Security & Access',
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
