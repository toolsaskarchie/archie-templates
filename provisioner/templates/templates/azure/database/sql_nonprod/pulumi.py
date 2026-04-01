"""
Azure SQL Database Non-Prod Template

Cost-optimized SQL Server + Database for dev/staging environments.
SQL Server + Single Database (Basic/S0) + Firewall Rules + TDE encryption.

Base cost (~$5-15/mo):
- 1 SQL Server (logical server)
- 1 SQL Database (Basic tier, 2GB)
- Transparent Data Encryption enabled
- Firewall rules for Azure services + optional client IP
"""

from typing import Any, Dict
import pulumi

from provisioner.templates.base import InfrastructureTemplate, template_registry
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory


@template_registry("azure-sql-nonprod")
class AzureSQLNonProdTemplate(InfrastructureTemplate):

    def __init__(self, name=None, config=None, **kwargs):
        raw_config = config or kwargs or {}
        if name is None:
            name = raw_config.get('project_name', 'azure-sql-nonprod')
        super().__init__(name, raw_config)

    def create_infrastructure(self):
        params = self.config.get('parameters', {})
        def cfg(key, default=None):
            return self.config.get(key) or params.get(key) or default

        project = cfg('project_name', 'myapp')
        env = cfg('environment', 'dev')
        location = cfg('location', 'eastus')
        team_name = cfg('team_name', '')
        admin_login = cfg('sql_admin_login', 'sqladmin')
        admin_password = cfg('sql_admin_password', '')
        db_name = cfg('database_name', f'{project}-{env}-db')
        sku_name = cfg('sku_name', 'Basic')
        max_size_gb = int(cfg('max_size_gb', '2'))
        allow_azure_services = cfg('allow_azure_services', 'true')
        if isinstance(allow_azure_services, str):
            allow_azure_services = allow_azure_services.lower() in ('true', '1', 'yes')
        client_ip = cfg('client_ip', '')

        tags = {
            'Project': project,
            'Environment': env,
            'ManagedBy': 'Archie',
            'Team': team_name or 'unassigned',
        }

        rg_name = cfg('resource_group_name') or f'rg-{project}-{env}'
        server_name = cfg('sql_server_name') or f'sql-{project}-{env}'

        # 1. Resource Group
        self.resource_group = factory.create('azure-native:resources:ResourceGroup', rg_name,
            resource_group_name=rg_name,
            location=location,
            tags=tags,
        )

        # 2. SQL Server
        server_props = {
            'server_name': server_name,
            'resource_group_name': self.resource_group.name,
            'location': location,
            'administrator_login': admin_login,
            'administrator_login_password': admin_password or f'{project}-Temp-P@ss-{env}',
            'version': '12.0',
            'minimal_tls_version': '1.2',
            'public_network_access': 'Enabled',
            'tags': tags,
        }
        self.server = factory.create('azure-native:sql:Server', server_name, **server_props)

        # 3. SQL Database
        sku_map = {
            'Basic': {'name': 'Basic', 'tier': 'Basic', 'capacity': 5},
            'S0': {'name': 'S0', 'tier': 'Standard', 'capacity': 10},
            'S1': {'name': 'S1', 'tier': 'Standard', 'capacity': 20},
        }
        db_sku = sku_map.get(sku_name, sku_map['Basic'])

        self.database = factory.create('azure-native:sql:Database', db_name,
            database_name=db_name,
            server_name=self.server.name,
            resource_group_name=self.resource_group.name,
            location=location,
            sku=db_sku,
            max_size_bytes=max_size_gb * 1024 * 1024 * 1024,
            tags=tags,
        )

        # 4. Firewall: Allow Azure services
        if allow_azure_services:
            factory.create('azure-native:sql:FirewallRule', f'{server_name}-allow-azure',
                firewall_rule_name='AllowAzureServices',
                server_name=self.server.name,
                resource_group_name=self.resource_group.name,
                start_ip_address='0.0.0.0',
                end_ip_address='0.0.0.0',
            )

        # 5. Firewall: Client IP (optional)
        if client_ip:
            factory.create('azure-native:sql:FirewallRule', f'{server_name}-client',
                firewall_rule_name='ClientIP',
                server_name=self.server.name,
                resource_group_name=self.resource_group.name,
                start_ip_address=client_ip,
                end_ip_address=client_ip,
            )

        # Exports
        pulumi.export('resource_group_name', rg_name)
        pulumi.export('sql_server_name', server_name)
        pulumi.export('sql_server_fqdn', pulumi.Output.concat(server_name, '.database.windows.net'))
        pulumi.export('database_name', db_name)
        pulumi.export('database_id', self.database.id)
        pulumi.export('connection_string', pulumi.Output.concat(
            'Server=tcp:', server_name, '.database.windows.net,1433;',
            'Initial Catalog=', db_name, ';',
            'Encrypt=True;TrustServerCertificate=False;'
        ))
        pulumi.export('team_name', team_name)

        return self.get_outputs()

    def get_outputs(self):
        return {
            'resource_group_name': self.resource_group.name if hasattr(self, 'resource_group') else None,
            'sql_server_name': self.server.name if hasattr(self, 'server') else None,
            'database_id': self.database.id if hasattr(self, 'database') else None,
        }

    @classmethod
    def get_metadata(cls):
        return {
            'name': 'azure-sql-nonprod',
            'title': 'SQL Database',
            'description': 'Cost-optimized Azure SQL Server with single database, TDE encryption, and firewall rules. For dev/staging workloads.',
            'category': 'database',
            'cloud': 'azure',
            'tier': 'standard',
            'environment': 'nonprod',
            'estimated_cost': '$5-15/month',
            'deployment_time': '3-5 minutes',
            'features': [
                'SQL Server with configurable admin credentials',
                'Single database with Basic/Standard SKU options',
                'TLS 1.2 minimum enforced',
                'Transparent Data Encryption (TDE) enabled by default',
                'Firewall rules for Azure services + optional client IP',
                'Connection string exported for app configuration',
            ],
            'tags': ['azure', 'database', 'sql', 'nonprod'],
        }
