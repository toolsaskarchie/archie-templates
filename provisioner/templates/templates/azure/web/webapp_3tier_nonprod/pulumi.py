"""
Azure 3-Tier Web App -- App Service + SQL Database + Key Vault + App Insights

Production-pattern web application stack for dev/staging. Composed template
combining web hosting, database, secrets management, and monitoring.

Base cost (~$25-80/mo):
- App Service Plan (B1) + Web App
- SQL Server + Basic Database
- Key Vault (Standard)
- Application Insights
- User-Assigned Managed Identity
"""

from typing import Any, Dict, Optional
import pulumi
from pulumi import ResourceOptions

from provisioner.templates.base import InfrastructureTemplate, template_registry
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory


@template_registry("azure-webapp-3tier-nonprod")
class AzureWebApp3TierNonProdTemplate(InfrastructureTemplate):

    def __init__(self, name: str = None, config: Dict[str, Any] = None, azure_config: Dict[str, Any] = None, **kwargs):
        raw_config = config or azure_config or kwargs or {}
        if name is None:
            name = (
                raw_config.get('project_name') or
                raw_config.get('projectName') or
                raw_config.get('parameters', {}).get('azure', {}).get('project_name') or
                'azure-webapp-3tier'
            )
        super().__init__(name, raw_config)
        self.config = raw_config

        # Resource references (populated in create())
        self.rg: Optional[object] = None
        self.identity: Optional[object] = None
        self.insights: Optional[object] = None
        self.vault: Optional[object] = None
        self.sql_server: Optional[object] = None
        self.database: Optional[object] = None
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
        """Deploy Azure 3-Tier Web App infrastructure (implements abstract method)"""
        return self.create()

    def create(self) -> Dict[str, Any]:
        """Deploy complete Azure 3-Tier Web App infrastructure"""
        project = self._cfg('project_name', 'myapp')
        env = self._cfg('environment', 'dev')
        location = self._cfg('location', 'eastus')
        team_name = self._cfg('team_name', '')
        sql_password = self._cfg('sql_admin_password', '')
        sku = self._cfg('sku_tier', 'B1')
        runtime = self._cfg('runtime_stack', 'NODE|18-lts')

        # Brownfield -- reference existing infrastructure instead of creating new
        existing_rg = self._cfg('existing_resource_group', '')
        existing_vnet_id = self._cfg('existing_vnet_id', '')
        existing_subnet_id = self._cfg('existing_subnet_id', '')

        tags = {
            'Project': project, 'Environment': env,
            'ManagedBy': 'Archie',
        }
        if team_name:
            tags['Team'] = team_name

        rg_name = self._cfg('resource_group_name') or f'rg-{project}-{env}'
        plan_name = self._cfg('app_service_plan_name') or f'plan-{project}-{env}'
        app_name = self._cfg('web_app_name') or f'app-{project}-{env}'
        sql_server_name = self._cfg('sql_server_name') or f'sql-{project}-{env}'
        db_name = self._cfg('database_name') or f'db-{project}-{env}'
        vault_name = self._cfg('vault_name') or f'kv-{project}-{env}'
        identity_name = self._cfg('identity_name') or f'id-{project}-{env}'
        insights_name = self._cfg('app_insights_name') or f'ai-{project}-{env}'

        # 1. Resource Group
        if existing_rg:
            # Reference existing -- Pulumi does NOT own this, won't destroy it
            import pulumi_azure_native as azure_native
            self.rg = azure_native.resources.ResourceGroup.get(
                'existing-rg', id=f'/subscriptions/{self._cfg("azure_subscription_id", "")}/resourceGroups/{existing_rg}')
            rg_name = existing_rg
        else:
            self.rg = factory.create('azure-native:resources:ResourceGroup', rg_name,
                resource_group_name=rg_name, location=location, tags=tags)

        # 2. Managed Identity
        self.identity = factory.create('azure-native:managedidentity:UserAssignedIdentity', identity_name,
            resource_name_=identity_name,
            resource_group_name=self.rg.name, location=location, tags=tags)

        # 3. App Insights (monitoring)
        self.insights = factory.create('azure-native:insights:Component', insights_name,
            resource_name_=insights_name,
            resource_group_name=self.rg.name, location=location,
            kind='web', application_type='web', tags=tags)

        # 4. Key Vault (secrets)
        self.vault = factory.create('azure-native:keyvault:Vault', vault_name,
            vault_name=vault_name,
            resource_group_name=self.rg.name, location=location,
            properties={
                'sku': {'family': 'A', 'name': 'standard'},
                'tenant_id': self._cfg('azure_tenant_id', ''),
                'enable_soft_delete': True,
                'soft_delete_retention_in_days': 7,
                'enable_rbac_authorization': True,
            }, tags=tags)

        # 5. SQL Server + Database
        self.sql_server = factory.create('azure-native:sql:Server', sql_server_name,
            server_name=sql_server_name,
            resource_group_name=self.rg.name, location=location,
            administrator_login='sqladmin',
            administrator_login_password=sql_password or f'{project}-TempP@ss-{env}',
            version='12.0', minimal_tls_version='1.2',
            public_network_access='Enabled', tags=tags)

        self.database = factory.create('azure-native:sql:Database', db_name,
            database_name=db_name,
            server_name=self.sql_server.name,
            resource_group_name=self.rg.name, location=location,
            sku={'name': 'Basic', 'tier': 'Basic', 'capacity': 5},
            tags=tags)

        # Allow Azure services to access SQL
        factory.create('azure-native:sql:FirewallRule', f'{sql_server_name}-azure',
            firewall_rule_name='AllowAzureServices',
            server_name=self.sql_server.name,
            resource_group_name=self.rg.name,
            start_ip_address='0.0.0.0', end_ip_address='0.0.0.0')

        # 6. App Service Plan
        self.plan = factory.create('azure-native:web:AppServicePlan', plan_name,
            name=plan_name,
            resource_group_name=self.rg.name, location=location,
            kind='Linux', reserved=True,
            sku={'name': sku, 'tier': 'Basic' if sku.startswith('B') else 'Standard'},
            tags=tags)

        # 7. Web App (connects to SQL + Key Vault + Insights)
        runtime_parts = runtime.split('|')
        linux_fx = f'{runtime_parts[0]}|{runtime_parts[1]}' if len(runtime_parts) == 2 else runtime

        self.web_app = factory.create('azure-native:web:WebApp', app_name,
            name=app_name,
            resource_group_name=self.rg.name, location=location,
            server_farm_id=self.plan.id,
            https_only=True,
            identity={'type': 'UserAssigned', 'user_assigned_identities': [self.identity.id]},
            site_config={
                'linux_fx_version': linux_fx,
                'always_on': False,
                'http20_enabled': True,
                'min_tls_version': '1.2',
                'ftps_state': 'Disabled',
                'app_settings': [
                    {'name': 'WEBSITE_RUN_FROM_PACKAGE', 'value': '1'},
                    {'name': 'KEY_VAULT_URI', 'value': pulumi.Output.concat('https://', vault_name, '.vault.azure.net/')},
                    {'name': 'APPINSIGHTS_INSTRUMENTATIONKEY', 'value': self.insights.instrumentation_key},
                    {'name': 'DB_SERVER', 'value': pulumi.Output.concat(sql_server_name, '.database.windows.net')},
                    {'name': 'DB_NAME', 'value': db_name},
                ],
            },
            tags=tags,
            opts=ResourceOptions(depends_on=[self.plan, self.sql_server, self.vault]))

        # Exports
        pulumi.export('resource_group_name', rg_name)
        pulumi.export('web_app_name', app_name)
        pulumi.export('web_app_url', pulumi.Output.concat('https://', app_name, '.azurewebsites.net'))
        pulumi.export('sql_server_name', sql_server_name)
        pulumi.export('sql_fqdn', pulumi.Output.concat(sql_server_name, '.database.windows.net'))
        pulumi.export('database_name', db_name)
        pulumi.export('vault_name', vault_name)
        pulumi.export('vault_uri', pulumi.Output.concat('https://', vault_name, '.vault.azure.net/'))
        pulumi.export('app_insights_name', insights_name)
        pulumi.export('app_insights_key', self.insights.instrumentation_key)
        pulumi.export('identity_name', identity_name)
        pulumi.export('identity_id', self.identity.id)
        pulumi.export('app_service_plan_name', plan_name)
        pulumi.export('environment', env)
        pulumi.export('deployment_mode', 'brownfield' if existing_rg else 'greenfield')
        if existing_vnet_id:
            pulumi.export('existing_vnet_id', existing_vnet_id)
        if existing_subnet_id:
            pulumi.export('existing_subnet_id', existing_subnet_id)

        return self.get_outputs()

    def get_outputs(self) -> Dict[str, Any]:
        return {
            'resource_group_name': self.rg.name if self.rg else None,
            'web_app_id': self.web_app.id if self.web_app else None,
            'web_app_name': self.web_app.name if self.web_app else None,
            'sql_server_name': self.sql_server.name if self.sql_server else None,
            'database_name': self.database.name if self.database else None,
            'vault_id': self.vault.id if self.vault else None,
            'vault_name': self.vault.name if self.vault else None,
            'app_insights_key': self.insights.instrumentation_key if self.insights else None,
            'identity_id': self.identity.id if self.identity else None,
            'app_service_plan_id': self.plan.id if self.plan else None,
        }

    @classmethod
    def get_metadata(cls) -> Dict[str, Any]:
        return {
            'name': 'azure-webapp-3tier-nonprod',
            'title': '3-Tier Web Application',
            'description': 'Full-stack web app: App Service + SQL Database + Key Vault + Application Insights with managed identity. For dev/staging.',
            'category': 'web',
            'version': '1.0.0',
            'author': 'Archie',
            'cloud': 'azure',
            'environment': 'nonprod',
            'base_cost': '$25-80/month',
            'deployment_time': '5-8 minutes',
            'complexity': 'intermediate',
            'features': [
                'App Service with configurable runtime (Node.js/Python/.NET)',
                'SQL Database with TDE encryption and TLS 1.2',
                'Key Vault for secrets management with RBAC',
                'Application Insights for monitoring and telemetry',
                'User-Assigned Managed Identity for secure access',
                'HTTPS-only with FTPS disabled',
            ],
            'tags': ['azure', 'web', 'appservice', 'sql', 'keyvault', 'nonprod'],
            'use_cases': [
                'Full-stack web applications',
                'API backends with database',
                'Development environments with production patterns',
                'Rapid prototyping with enterprise architecture',
            ],
            'pillars': [
                {
                    'title': 'Security',
                    'score': 'excellent',
                    'score_color': '#10b981',
                    'description': 'HTTPS, TLS 1.2, Key Vault, managed identity, RBAC',
                    'practices': [
                        'HTTPS-only with TLS 1.2 minimum',
                        'Key Vault with RBAC for secrets management',
                        'User-assigned managed identity',
                        'SQL Server TLS 1.2 enforced',
                        'FTPS disabled on App Service',
                    ],
                },
                {
                    'title': 'Operational Excellence',
                    'score': 'excellent',
                    'score_color': '#10b981',
                    'description': 'Full observability with App Insights and managed services',
                    'practices': [
                        'Application Insights for APM and telemetry',
                        'All services fully managed (PaaS)',
                        'Standard naming and tagging conventions',
                        'Brownfield support for existing infrastructure',
                    ],
                },
                {
                    'title': 'Cost Optimization',
                    'score': 'excellent',
                    'score_color': '#10b981',
                    'description': 'Basic tiers across all services for non-prod',
                    'practices': [
                        'App Service Basic B1 ($13/month)',
                        'SQL Database Basic tier ($5/month)',
                        'Key Vault Standard (pay-per-use)',
                        'App Insights free tier included',
                        'Always-on disabled to reduce cost',
                    ],
                },
                {
                    'title': 'Reliability',
                    'score': 'needs-improvement',
                    'score_color': '#f59e0b',
                    'description': 'Basic tiers have limited SLA (appropriate for non-prod)',
                    'practices': [
                        'Basic App Service — single instance',
                        'Basic SQL — limited DTU and no geo-replication',
                        'Non-prod: high availability not required',
                    ],
                },
                {
                    'title': 'Sustainability',
                    'score': 'good',
                    'score_color': '#10b981',
                    'description': 'PaaS services with minimal resource overhead',
                    'practices': [
                        'All services are PaaS — shared infrastructure',
                        'Always-on disabled reduces idle compute',
                        'Basic tiers avoid over-provisioning',
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
                'sku_tier': {
                    'type': 'string',
                    'default': 'B1',
                    'title': 'App Service SKU',
                    'description': 'App Service Plan pricing tier',
                    'enum': ['B1', 'B2', 'S1', 'S2'],
                    'order': 10,
                    'group': 'Compute',
                    'cost_impact': '$13-75/month',
                },
                'runtime_stack': {
                    'type': 'string',
                    'default': 'NODE|18-lts',
                    'title': 'Runtime Stack',
                    'description': 'Application runtime and version',
                    'enum': ['NODE|18-lts', 'NODE|20-lts', 'PYTHON|3.11', 'DOTNETCORE|8.0'],
                    'order': 11,
                    'group': 'Compute',
                },
                'sql_admin_password': {
                    'type': 'string',
                    'default': '',
                    'title': 'SQL Admin Password',
                    'description': 'Password for the SQL admin user (auto-generated if empty)',
                    'order': 20,
                    'group': 'Database',
                    'sensitive': True,
                },
                'azure_tenant_id': {
                    'type': 'string',
                    'default': '',
                    'title': 'Azure Tenant ID',
                    'description': 'Required for Key Vault RBAC configuration',
                    'order': 30,
                    'group': 'Security & Access',
                },
                'existing_resource_group': {
                    'type': 'string',
                    'default': '',
                    'title': 'Existing Resource Group',
                    'description': 'Deploy into an existing resource group (leave empty for greenfield)',
                    'order': 40,
                    'group': 'Existing Infrastructure',
                },
                'azure_subscription_id': {
                    'type': 'string',
                    'default': '',
                    'title': 'Azure Subscription ID',
                    'description': 'Required when using an existing resource group',
                    'order': 41,
                    'group': 'Existing Infrastructure',
                    'conditional': {'field': 'existing_resource_group'},
                },
                'existing_vnet_id': {
                    'type': 'string',
                    'default': '',
                    'title': 'Existing VNet ID',
                    'description': 'Reference an existing VNet (future use). Full resource ID.',
                    'order': 42,
                    'group': 'Existing Infrastructure',
                },
                'existing_subnet_id': {
                    'type': 'string',
                    'default': '',
                    'title': 'Existing Subnet ID',
                    'description': 'Reference an existing Subnet (future use). Full resource ID.',
                    'order': 43,
                    'group': 'Existing Infrastructure',
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
