import pulumi
import pulumi_azure_native as azure_native
from provisioner.templates.base import InfrastructureTemplate, template_registry
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory
from provisioner.utils.azure.password import gen_sql_password

@template_registry("azure-sql-app-data")
class AzureSqlAppDataTemplate(InfrastructureTemplate):
    def __init__(self, name=None, config=None, **kwargs):
        raw_config = config or kwargs or {}
        if name is None:
            name = raw_config.get('project_name', 'azure-sql-app-data')
        super().__init__(name, raw_config)

    def create_infrastructure(self):
        params = self.config.get('parameters', {})
        def cfg(key, default=None):
            return self.config.get(key) or params.get(key) or default

        tags = {
            'Project': cfg('project_name', 'myapp'),
            'Environment': cfg('environment', 'dev'),
            'ManagedBy': 'Pulumi'
        }

        self.resource_group = factory.create('azure-native:resources:ResourceGroup', 'main-resource-group',
            resource_group_name='rg-data',
            location='eastus',
            tags=tags
        )

        self.main_server = factory.create('azure-native:sql:Server', 'main-sql-server',
            server_name='sql-myapp',
            resource_group_name=self.resource_group.name,
            location='eastus',
            version='12.0',
            administrator_login='sqladmin',
            administrator_login_password=gen_sql_password(),
            minimal_tls_version='1.2'
        )

        self.main_database = factory.create('azure-native:sql:Database', 'main-database',
            database_name='db-myapp',
            server_name=self.main_server.name,
            resource_group_name=self.resource_group.name,
            sku={
                'name': 'Basic',
                'tier': 'Basic'
            }
        )

        self.main_key_vault = factory.create('azure-native:keyvault:Vault', 'main-key-vault',
            vault_name='kv-myapp',
            resource_group_name=self.resource_group.name,
            location='eastus',
            properties={
                'tenant_id': '00000000-0000-0000-0000-000000000000',
                'sku': {
                    'family': 'A', 
                    'name': 'standard'
                },
                'soft_delete_retention_in_days': 7
            }
        )

        pulumi.export('resource_group_name', self.resource_group.name)
        pulumi.export('sql_server_name', self.main_server.name)
        pulumi.export('database_name', self.main_database.name)
        pulumi.export('key_vault_name', self.main_key_vault.name)

        return self.get_outputs()

    def get_outputs(self):
        return {
            'resource_group_name': self.resource_group.name if hasattr(self, 'resource_group') else None,
            'sql_server_name': self.main_server.name if hasattr(self, 'main_server') else None,
            'database_name': self.main_database.name if hasattr(self, 'main_database') else None,
            'key_vault_name': self.main_key_vault.name if hasattr(self, 'main_key_vault') else None
        }

    @classmethod
    def get_metadata(cls):
        return {
            'name': 'azure-sql-app-data',
            'title': 'Azure SQL Application Data Infrastructure',
            'description': 'Provision a resource group, SQL server, database, and key vault for application data storage',
            'category': 'database',
            'cloud': 'azure',
            'tier': 'standard',
            'estimated_cost': '$50-100/mo',
            'deployment_time': '~10 min',
            'features': [
                'SQL Database', 
                'Key Vault', 
                'Resource Group'
            ],
            'use_cases': [
                'Application backend data storage',
                'Database hosting',
                'Secure secret management'
            ],
            'pillars': [
                'Security',
                'Performance',
                'Cost Optimization'
            ],
            'resources': [
                {
                    'name': 'Resource Group',
                    'type': 'azure-native:resources:ResourceGroup',
                    'category': 'Management',
                    'description': 'Container for related Azure resources'
                },
                {
                    'name': 'SQL Server',
                    'type': 'azure-native:sql:Server',
                    'category': 'Database',
                    'description': 'Managed SQL database server'
                },
                {
                    'name': 'SQL Database',
                    'type': 'azure-native:sql:Database',
                    'category': 'Database',
                    'description': 'Basic-tier SQL database'
                },
                {
                    'name': 'Key Vault',
                    'type': 'azure-native:keyvault:Vault',
                    'category': 'Security',
                    'description': 'Secure secret and key management'
                }
            ],
            'config_fields': [
                {
                    'name': 'project_name',
                    'type': 'text',
                    'label': 'Project Name',
                    'required': True,
                    'default': 'myapp',
                    'group': 'General',
                    'helpText': 'Name of the project or application'
                },
                {
                    'name': 'environment',
                    'type': 'select',
                    'label': 'Environment',
                    'required': True,
                    'default': 'dev',
                    'group': 'General',
                    'options': ['dev', 'staging', 'prod'],
                    'helpText': 'Deployment environment'
                },
                {
                    'name': 'location',
                    'type': 'select',
                    'label': 'Azure Region',
                    'required': True,
                    'default': 'eastus',
                    'group': 'General',
                    'options': ['eastus', 'westus', 'centralus', 'northeurope', 'westeurope'],
                    'helpText': 'Azure region for resource deployment'
                }
            ]
        }
