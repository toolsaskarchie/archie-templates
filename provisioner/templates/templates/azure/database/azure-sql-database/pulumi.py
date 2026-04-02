import pulumi
import pulumi_azure_native as azure_native
from provisioner.templates.base import InfrastructureTemplate, template_registry
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory

@template_registry("azure-sql-database")
class AzureSqlDatabase(InfrastructureTemplate):
    def __init__(self, name=None, config=None, **kwargs):
        raw_config = config or kwargs or {}
        if name is None:
            name = raw_config.get('project_name', 'azure-sql-database')
        super().__init__(name, raw_config)

    def create_infrastructure(self):
        params = self.config.get('parameters', {})
        def cfg(key, default=None):
            return self.config.get(key) or params.get(key) or default

        project = cfg('project_name', 'myapp')
        env = cfg('environment', 'dev')
        location = cfg('location', 'eastus')
        tenant_id = cfg('azure_tenant_id', '00000000-0000-0000-0000-000000000000')

        tags = {
            'Project': project,
            'Environment': env,
            'ManagedBy': 'Pulumi'
        }

        self.resource_group = factory.create('azure-native:resources:ResourceGroup', f'azure-rg-{project}-{env}',
            resource_group_name=f'rg-{project}',
            location=location,
            tags=tags
        )

        self.sql_server = factory.create('azure-native:sql:Server', f'azure-sqlserver-{project}-{env}',
            server_name=f'sql-{project}',
            resource_group_name=self.resource_group.name,
            location=location,
            version='12.0',
            administrator_login=cfg('sql_admin_username', 'sqladmin'),
            administrator_login_password=cfg('sql_admin_password', 'P@ssw0rd!2024'),
            minimal_tls_version='1.2',
            tags=tags
        )

        self.sql_database = factory.create('azure-native:sql:Database', f'azure-sqldb-{project}-{env}',
            database_name=f'db-{project}',
            resource_group_name=self.resource_group.name,
            server_name=self.sql_server.name,
            sku={
                'name': 'Basic',
                'tier': 'Basic',
                'capacity': 5
            },
            tags=tags
        )

        self.key_vault = factory.create('azure-native:keyvault:Vault', f'azure-kv-{project}-{env}',
            vault_name=f'kv-{project}',
            resource_group_name=self.resource_group.name,
            location=location,
            properties={
                'tenant_id': tenant_id,
                'sku': {'family': 'A', 'name': 'standard'},
                'soft_delete_retention_in_days': 7
            },
            tags=tags
        )

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
            'name': 'azure-sql-database',
            'title': 'Azure SQL Database Setup',
            'description': 'Deploy an Azure resource group with SQL server, database, and key vault',
            'category': 'database',
            'cloud': 'azure',
            'tier': 'standard',
            'estimated_cost': '$50-200/mo',
            'deployment_time': '~10 min',
            'features': ['SQL Database', 'Key Vault'],
            'use_cases': ['Application Backend', 'Data Storage'],
            'pillars': ['Security', 'Performance', 'Cost Optimization'],
            'resources': [
                {'name': 'Resource Group', 'type': 'azure-native:resources:ResourceGroup', 'category': 'Management', 'description': 'Container for Azure resources'},
                {'name': 'SQL Server', 'type': 'azure-native:sql:Server', 'category': 'Database', 'description': 'Managed SQL server instance'},
                {'name': 'SQL Database', 'type': 'azure-native:sql:Database', 'category': 'Database', 'description': 'SQL database instance'},
                {'name': 'Key Vault', 'type': 'azure-native:keyvault:Vault', 'category': 'Security', 'description': 'Secret and key management'}
            ],
            'config_fields': [
                {'name': 'project_name', 'type': 'text', 'label': 'Project Name', 'required': true, 'default': 'myapp', 'group': 'General', 'helpText': 'Name of the project'},
                {'name': 'location', 'type': 'select', 'label': 'Azure Region', 'required': true, 'default': 'eastus', 'group': 'General', 'helpText': 'Azure region for resources', 'options': ['eastus', 'westus', 'northeurope', 'westeurope']},
                {'name': 'sql_admin_username', 'type': 'text', 'label': 'SQL Admin Username', 'required': true, 'default': 'sqladmin', 'group': 'Database', 'helpText': 'Administrator username for SQL server'},
                {'name': 'sql_admin_password', 'type': 'text', 'label': 'SQL Admin Password', 'required': true, 'group': 'Database', 'helpText': 'Administrator password for SQL server'},
                {'name': 'azure_tenant_id', 'type': 'text', 'label': 'Azure Tenant ID', 'required': true, 'default': '00000000-0000-0000-0000-000000000000', 'group': 'Security', 'helpText': 'Azure Active Directory tenant ID'}
            ]
        }
