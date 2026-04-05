"""
Azure 3-Tier Web App — App Service + SQL Database + Key Vault + App Insights

Production-pattern web application stack for dev/staging. Composed template
combining web hosting, database, secrets management, and monitoring.

Base cost (~$25-80/mo):
- App Service Plan (B1) + Web App
- SQL Server + Basic Database
- Key Vault (Standard)
- Application Insights
- User-Assigned Managed Identity
"""

from typing import Any, Dict
import pulumi
from pulumi import ResourceOptions

from provisioner.templates.base import InfrastructureTemplate, template_registry
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory


@template_registry("azure-webapp-3tier-nonprod")
class AzureWebApp3TierNonProdTemplate(InfrastructureTemplate):

    def __init__(self, name=None, config=None, **kwargs):
        raw_config = config or kwargs or {}
        if name is None:
            name = raw_config.get('project_name', 'azure-webapp-3tier')
        super().__init__(name, raw_config)

    def create_infrastructure(self):
        params = self.config.get('parameters', {})
        def cfg(key, default=None):
            return self.config.get(key) or params.get(key) or default

        project = cfg('project_name', 'myapp')
        env = cfg('environment', 'dev')
        location = cfg('location', 'eastus')
        team_name = cfg('team_name', '')
        sql_password = cfg('sql_admin_password', '')
        sku = cfg('sku_tier', 'B1')
        runtime = cfg('runtime_stack', 'NODE|18-lts')

        # Brownfield — reference existing infrastructure instead of creating new
        existing_rg = cfg('existing_resource_group', '')
        existing_vnet_id = cfg('existing_vnet_id', '')
        existing_subnet_id = cfg('existing_subnet_id', '')

        tags = {
            'Project': project, 'Environment': env,
            'ManagedBy': 'Archie', 'Team': team_name or 'unassigned',
        }

        rg_name = cfg('resource_group_name') or f'rg-{project}-{env}'
        plan_name = cfg('app_service_plan_name') or f'plan-{project}-{env}'
        app_name = cfg('web_app_name') or f'app-{project}-{env}'
        sql_server_name = cfg('sql_server_name') or f'sql-{project}-{env}'
        db_name = cfg('database_name') or f'db-{project}-{env}'
        vault_name = cfg('vault_name') or f'kv-{project}-{env}'
        identity_name = cfg('identity_name') or f'id-{project}-{env}'
        insights_name = cfg('app_insights_name') or f'ai-{project}-{env}'

        # 1. Resource Group
        if existing_rg:
            # Reference existing — Pulumi does NOT own this, won't destroy it
            import pulumi_azure_native as azure_native
            self.rg = azure_native.resources.ResourceGroup.get(
                'existing-rg', id=f'/subscriptions/{cfg("azure_subscription_id", "")}/resourceGroups/{existing_rg}')
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
                'tenant_id': cfg('azure_tenant_id', ''),
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
        pulumi.export('web_app_url', pulumi.Output.concat('https://', app_name, '.azurewebsites.net'))
        pulumi.export('sql_fqdn', pulumi.Output.concat(sql_server_name, '.database.windows.net'))
        pulumi.export('database_name', db_name)
        pulumi.export('vault_uri', pulumi.Output.concat('https://', vault_name, '.vault.azure.net/'))
        pulumi.export('app_insights_key', self.insights.instrumentation_key)
        pulumi.export('identity_id', self.identity.id)
        pulumi.export('team_name', team_name)
        pulumi.export('deployment_mode', 'brownfield' if existing_rg else 'greenfield')
        if existing_vnet_id:
            pulumi.export('existing_vnet_id', existing_vnet_id)
        if existing_subnet_id:
            pulumi.export('existing_subnet_id', existing_subnet_id)

        return self.get_outputs()

    def get_outputs(self):
        return {
            'resource_group_name': self.rg.name if hasattr(self, 'rg') else None,
            'web_app_id': self.web_app.id if hasattr(self, 'web_app') else None,
            'sql_server_name': self.sql_server.name if hasattr(self, 'sql_server') else None,
            'vault_id': self.vault.id if hasattr(self, 'vault') else None,
        }

    @classmethod
    def get_metadata(cls):
        return {
            'name': 'azure-webapp-3tier-nonprod',
            'title': '3-Tier Web Application',
            'description': 'Full-stack web app: App Service + SQL Database + Key Vault + Application Insights with managed identity. For dev/staging.',
            'category': 'web',
            'cloud': 'azure',
            'tier': 'standard',
            'environment': 'nonprod',
            'estimated_cost': '$25-80/month',
            'deployment_time': '5-8 minutes',
            'features': [
                'App Service with configurable runtime (Node.js/Python/.NET)',
                'SQL Database with TDE encryption and TLS 1.2',
                'Key Vault for secrets management with RBAC',
                'Application Insights for monitoring and telemetry',
                'User-Assigned Managed Identity for secure access',
                'HTTPS-only with FTPS disabled',
            ],
            'tags': ['azure', 'web', 'appservice', 'sql', 'keyvault', 'nonprod'],
            'config_fields': [
                {'key': 'project_name', 'label': 'Project Name', 'type': 'text', 'required': True, 'group': 'Basic'},
                {'key': 'environment', 'label': 'Environment', 'type': 'select', 'options': ['dev', 'staging'], 'default': 'dev', 'group': 'Basic'},
                {'key': 'location', 'label': 'Azure Region', 'type': 'text', 'default': 'eastus', 'group': 'Basic'},
                {'key': 'team_name', 'label': 'Team Name', 'type': 'text', 'group': 'Basic'},
                {'key': 'sku_tier', 'label': 'App Service SKU', 'type': 'select', 'options': ['B1', 'B2', 'S1', 'S2'], 'default': 'B1', 'group': 'Compute'},
                {'key': 'runtime_stack', 'label': 'Runtime Stack', 'type': 'select', 'options': ['NODE|18-lts', 'NODE|20-lts', 'PYTHON|3.11', 'DOTNETCORE|8.0'], 'default': 'NODE|18-lts', 'group': 'Compute'},
                {'key': 'sql_admin_password', 'label': 'SQL Admin Password', 'type': 'text', 'required': True, 'group': 'Database'},
                {'key': 'resource_group_name', 'label': 'Resource Group Name', 'type': 'text', 'group': 'Naming'},
                {'key': 'app_service_plan_name', 'label': 'App Service Plan Name', 'type': 'text', 'group': 'Naming'},
                {'key': 'web_app_name', 'label': 'Web App Name', 'type': 'text', 'group': 'Naming'},
                {'key': 'sql_server_name', 'label': 'SQL Server Name', 'type': 'text', 'group': 'Naming'},
                {'key': 'database_name', 'label': 'Database Name', 'type': 'text', 'group': 'Naming'},
                {'key': 'vault_name', 'label': 'Key Vault Name', 'type': 'text', 'group': 'Naming'},
                {'key': 'identity_name', 'label': 'Managed Identity Name', 'type': 'text', 'group': 'Naming'},
                {'key': 'app_insights_name', 'label': 'App Insights Name', 'type': 'text', 'group': 'Naming'},
                {'key': 'azure_tenant_id', 'label': 'Azure Tenant ID', 'type': 'text', 'group': 'Security'},
                {'key': 'azure_subscription_id', 'label': 'Azure Subscription ID', 'type': 'text', 'group': 'Security'},
                {'key': 'existing_resource_group', 'label': 'Existing Resource Group', 'type': 'text', 'group': 'Existing Infrastructure', 'description': 'Use an existing RG instead of creating one. Leave blank for greenfield.'},
                {'key': 'existing_vnet_id', 'label': 'Existing VNet ID', 'type': 'text', 'group': 'Existing Infrastructure', 'description': 'Reference an existing VNet (future use). Full resource ID.'},
                {'key': 'existing_subnet_id', 'label': 'Existing Subnet ID', 'type': 'text', 'group': 'Existing Infrastructure', 'description': 'Reference an existing Subnet (future use). Full resource ID.'},
            ],
        }
