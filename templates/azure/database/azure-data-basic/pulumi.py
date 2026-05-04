import pulumi
import pulumi_azure_native as azure_native
from provisioner.templates.base import InfrastructureTemplate, template_registry
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory
from provisioner.utils.azure.password import gen_sql_password

@template_registry("azure-data-basic")
class AzureDataBasicTemplate(InfrastructureTemplate):
    def __init__(self, name=None, config=None, **kwargs):
        raw_config = config or kwargs or {}
        if name is None:
            name = raw_config.get('project_name', 'azure-data-basic')
        super().__init__(name, raw_config)

    def create_infrastructure(self):
        params = self.config.get('parameters', {})
        def cfg(key, default=None):
            return self.config.get(key) or params.get(key) or default

        project = cfg('project_name', 'myapp')
        env = cfg('environment', 'dev')
        location = cfg('location', 'eastus')

        tags = {
            'Project': project,
            'Environment': env,
            'ManagedBy': 'Pulumi'
        }

        self.resource_group = factory.create('azure-native:resources:ResourceGroup', f'rg-{project}-{env}',
            location=location,
            resource_group_name=f'rg-{project}-{env}',
            tags=tags
        )

        self.sql_server = factory.create('azure-native:sql:Server', f'sql-{project}-{env}',
            location=location,
            resource_group_name=self.resource_group.name,
            version='12.0',
            administrator_login=cfg('sql_admin_username', 'sqladmin'),
            administrator_login_password=cfg('sql_admin_password') or gen_sql_password(),
            minimal_tls_version='1.2'
        )

        self.sql_database = factory.create('azure-native:sql:Database', f'db-{project}-{env}',
            location=location,
            resource_group_name=self.resource_group.name,
            server_name=self.sql_server.name,
            sku={'name': 'Basic', 'tier': 'Basic', 'capacity': 5}
        )

        self.key_vault = factory.create('azure-native:keyvault:Vault', f'kv-{project}-{env}',
            resource_group_name=self.resource_group.name,
            location=location,
            properties={
                'tenant_id': cfg('azure_tenant_id', '00000000-0000-0000-0000-000000000000'),
                'sku': {'family': 'A', 'name': 'standard'},
                'soft_delete_retention_in_days': 7
            },
            tags=tags
        )

        # Exports
        pulumi.export('resource_group_name', self.resource_group.name)
        pulumi.export('sql_server_name', self.sql_server.name)
        pulumi.export('sql_database_name', self.sql_database.name)
        pulumi.export('key_vault_name', self.key_vault.name)

        return self.get_outputs()

    def get_outputs(self):
        return {
            'resource_group_name': self.resource_group.name if hasattr(self, 'resource_group') else None,
            'sql_server_name': self.sql_server.name if hasattr(self, 'sql_server') else None,
            'sql_database_name': self.sql_database.name if hasattr(self, 'sql_database') else None,
            'key_vault_name': self.key_vault.name if hasattr(self, 'key_vault') else None
        }

    @classmethod
    def get_metadata(cls):
        return {
            'name': 'azure-data-basic',
            'title': 'Basic Azure Data Resources',
            'description': 'Deploys an Azure resource group with a SQL database and key vault for basic data storage and secrets management.',
            'category': 'database',
            'cloud': 'azure',
            'tier': 'standard',
            'estimated_cost': '$50-100/mo',
            'deployment_time': '~10 minutes',
            'features': [
                'Azure Resource Group',
                'SQL Server Database',
                'Key Vault for Secret Management',
                'Configured with Basic SKU'
            ],
            'use_cases': [
                'Small to medium data storage',
                'Development and testing environments',
                'Lightweight application backend'
            ],
            'pillars': [
                {'title': 'Security', 'description': 'TLS 1.2 enforced, key vault for secret management'},
                {'title': 'Reliability', 'description': 'Basic resources with standard configuration'},
                {'title': 'Cost Optimization', 'description': 'Lowest tier resources selected'},
                {'title': 'Operational Excellence', 'description': 'Standardized resource naming and tagging'},
                {'title': 'Performance Efficiency', 'description': 'Suitable for low-traffic applications'},
                {'title': 'Sustainability', 'description': 'Minimal resource footprint'}
            ],
            'resources': [
                {'name': 'ResourceGroup', 'type': 'azure-native:resources:ResourceGroup', 'category': 'Core', 'description': 'Container for all resources'},
                {'name': 'SQLServer', 'type': 'azure-native:sql:Server', 'category': 'Database', 'description': 'SQL database server instance'},
                {'name': 'SQLDatabase', 'type': 'azure-native:sql:Database', 'category': 'Database', 'description': 'Basic tier SQL database'},
                {'name': 'KeyVault', 'type': 'azure-native:keyvault:Vault', 'category': 'Security', 'description': 'Secret and key management vault'}
            ],
            'config_fields': [
                {'name': 'project_name', 'type': 'text', 'label': 'Project Name', 'required': true, 'default': 'myapp', 'group': 'General', 'helpText': 'Name of the project or application'},
                {'name': 'environment', 'type': 'text', 'label': 'Environment', 'required': true, 'default': 'dev', 'group': 'General', 'helpText': 'Deployment environment (dev/staging/prod)'},
                {'name': 'location', 'type': 'text', 'label': 'Azure Region', 'required': true, 'default': 'eastus', 'group': 'Network', 'helpText': 'Azure region for resource deployment'},
                {'name': 'sql_admin_username', 'type': 'text', 'label': 'SQL Admin Username', 'required': true, 'default': 'sqladmin', 'group': 'Database', 'helpText': 'Administrator username for SQL server'},
                {'name': 'sql_admin_password', 'type': 'text', 'label': 'SQL Admin Password', 'required': true, 'default': '', 'group': 'Database', 'helpText': 'Administrator password for SQL server'},
                {'name': 'azure_tenant_id', 'type': 'text', 'label': 'Azure Tenant ID', 'required': true, 'default': '00000000-0000-0000-0000-000000000000', 'group': 'Security', 'helpText': 'Azure Active Directory tenant ID'}
            ]
        }
