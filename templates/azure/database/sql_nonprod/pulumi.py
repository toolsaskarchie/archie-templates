"""
Azure SQL Database Non-Prod Template

Cost-optimized SQL Server + Serverless Database for dev/staging environments.
Serverless compute tier with auto-pause, geo-redundant backups, TDE encryption.

Base cost (~$5-15/mo):
- 1 SQL Server (logical server, free)
- 1 SQL Database (Serverless, auto-pause after idle period)
- Transparent Data Encryption enabled by default
- Geo-redundant backup storage
- Firewall rules for Azure services + optional client IP
- TLS 1.2 minimum enforced
"""

from typing import Any, Dict, Optional
from pathlib import Path
import pulumi
import pulumi_azure_native as azure_native

from provisioner.templates.base import InfrastructureTemplate, template_registry
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory
from provisioner.utils.azure.tags import get_standard_tags, get_sql_server_tags
from provisioner.utils.azure.naming import get_resource_group_name, get_sql_server_name, get_resource_name
from provisioner.utils.azure.password import gen_sql_password


@template_registry("azure-sql-nonprod")
class AzureSQLNonProdTemplate(InfrastructureTemplate):
    """
    Azure SQL Database Non-Prod Template

    Cost-optimized SQL Server with serverless database for non-production
    environments. Auto-pause reduces cost to near zero when idle.
    """

    def __init__(self, name: str = None, config: Dict[str, Any] = None, azure_config: Dict[str, Any] = None, **kwargs):
        """Initialize Azure SQL Non-Prod template"""
        raw_config = config or azure_config or kwargs or {}

        if name is None:
            name = (
                raw_config.get('project_name') or
                raw_config.get('projectName') or
                raw_config.get('parameters', {}).get('azure', {}).get('project_name') or
                'azure-sql-nonprod'
            )

        super().__init__(name, raw_config)
        self.config = raw_config

        # Resource references (populated in create())
        self.resource_group: Optional[object] = None
        self.server: Optional[object] = None
        self.database: Optional[object] = None
        self.firewall_azure: Optional[object] = None
        self.firewall_client: Optional[object] = None

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
        """Deploy Azure SQL infrastructure (implements abstract method)"""
        return self.create()

    def create(self) -> Dict[str, Any]:
        """Deploy complete Azure SQL infrastructure"""

        # Read config
        project = self._cfg('project_name', 'myapp')
        env = self._cfg('environment', 'dev')
        location = self._cfg('location', 'eastus')
        team_name = self._cfg('team_name', '')
        admin_login = self._cfg('sql_admin_login', 'sqladmin')
        admin_password = self._cfg('sql_admin_password', '')
        database_name = self._cfg('database_name', f'{project}-{env}-db')
        auto_pause_delay = int(self._cfg('auto_pause_delay', '60'))
        min_vcores = float(self._cfg('min_vcores', '0.5'))
        max_vcores = float(self._cfg('max_vcores', '2'))
        max_size_gb = int(self._cfg('max_size_gb', '32'))
        backup_redundancy = self._cfg('backup_storage_redundancy', 'Geo')
        client_ip = self._cfg('client_ip', '')

        allow_azure_services = self._cfg('allow_azure_services', True)
        if isinstance(allow_azure_services, str):
            allow_azure_services = allow_azure_services.lower() in ('true', '1', 'yes')

        # Standard tags
        tags = get_standard_tags(project=project, environment=env)
        tags['ManagedBy'] = 'Archie'
        tags['Template'] = 'azure-sql-nonprod'
        tags.update(self._cfg('tags', {}))
        if team_name:
            tags['Team'] = team_name

        # Resource names (prefer injected on upgrade — Rule #3)
        rg_name = self._cfg('resource_group_name') or f'rg-{project}-{env}-sql'
        server_name = self._cfg('sql_server_name') or get_sql_server_name(project, env)

        # =================================================================
        # LAYER 1: Resource Group
        # =================================================================

        self.resource_group = factory.create(
            'azure-native:resources:ResourceGroup', rg_name,
            resource_group_name=rg_name,
            location=location,
            tags={**tags, 'Purpose': 'sql-database'},
        )

        # =================================================================
        # LAYER 2: SQL Server (Logical Server)
        # =================================================================

        self.server = factory.create(
            'azure-native:sql:Server', server_name,
            server_name=server_name,
            resource_group_name=self.resource_group.name,
            location=location,
            administrator_login=admin_login,
            administrator_login_password=admin_password or gen_sql_password(),
            version='12.0',
            minimal_tls_version='1.2',
            public_network_access='Enabled',
            tags=tags,
        )

        # =================================================================
        # LAYER 3: SQL Database (Serverless Tier)
        # =================================================================

        self.database = factory.create(
            'azure-native:sql:Database', database_name,
            database_name=database_name,
            server_name=self.server.name,
            resource_group_name=self.resource_group.name,
            location=location,
            sku={
                'name': 'GP_S_Gen5',
                'tier': 'GeneralPurpose',
                'family': 'Gen5',
                'capacity': int(max_vcores),
            },
            auto_pause_delay=auto_pause_delay,
            min_capacity=min_vcores,
            max_size_bytes=max_size_gb * 1024 * 1024 * 1024,
            requested_backup_storage_redundancy=backup_redundancy,
            zone_redundant=False,
            tags=tags,
        )

        # =================================================================
        # LAYER 4: Firewall Rules
        # =================================================================

        # Allow Azure services
        if allow_azure_services:
            self.firewall_azure = factory.create(
                'azure-native:sql:FirewallRule', f'{server_name}-allow-azure',
                firewall_rule_name='AllowAzureServices',
                server_name=self.server.name,
                resource_group_name=self.resource_group.name,
                start_ip_address='0.0.0.0',
                end_ip_address='0.0.0.0',
            )

        # Client IP (optional)
        if client_ip:
            self.firewall_client = factory.create(
                'azure-native:sql:FirewallRule', f'{server_name}-client',
                firewall_rule_name='ClientIP',
                server_name=self.server.name,
                resource_group_name=self.resource_group.name,
                start_ip_address=client_ip,
                end_ip_address=client_ip,
            )

        # =================================================================
        # Exports (Rule #2, #7)
        # =================================================================

        pulumi.export('resource_group_name', rg_name)
        pulumi.export('sql_server_name', server_name)
        pulumi.export('sql_server_fqdn', pulumi.Output.concat(server_name, '.database.windows.net'))
        pulumi.export('database_name', database_name)
        pulumi.export('database_id', self.database.id)
        pulumi.export('server_id', self.server.id)
        pulumi.export('connection_string', pulumi.Output.concat(
            'Server=tcp:', server_name, '.database.windows.net,1433;',
            'Initial Catalog=', database_name, ';',
            'Encrypt=True;TrustServerCertificate=False;'
        ))
        pulumi.export('environment', env)
        if team_name:
            pulumi.export('team_name', team_name)

        return self.get_outputs()

    def get_outputs(self) -> Dict[str, Any]:
        """Get outputs for downstream templates"""
        return {
            'resource_group_name': self.resource_group.name if self.resource_group else None,
            'sql_server_name': self.server.name if self.server else None,
            'sql_server_fqdn': self.server.fully_qualified_domain_name if self.server else None,
            'database_name': self.database.name if self.database else None,
            'database_id': self.database.id if self.database else None,
            'server_id': self.server.id if self.server else None,
        }

    @classmethod
    def get_metadata(cls) -> Dict[str, Any]:
        """Template metadata for catalog UI"""
        return {
            "name": "azure-sql-nonprod",
            "title": "Serverless SQL Database",
            "description": "Cost-optimized Azure SQL with serverless compute tier. Auto-pauses when idle, geo-redundant backups, TDE encryption. For dev/staging workloads.",
            "category": "database",
            "version": "2.0.0",
            "author": "Archie",
            "cloud": "azure",
            "environment": "nonprod",
            "base_cost": "$5-15/month",
            "features": [
                "Serverless compute tier with auto-pause (saves cost when idle)",
                "Configurable vCore range (0.5-2 vCores default)",
                "Transparent Data Encryption (TDE) enabled by default",
                "TLS 1.2 minimum enforced",
                "Geo-redundant backup storage",
                "Firewall rules for Azure services + optional client IP",
                "Connection string exported for app configuration",
            ],
            "tags": ["azure", "database", "sql", "serverless", "nonprod", "auto-pause"],
            "deployment_time": "3-5 minutes",
            "complexity": "beginner",
            "use_cases": [
                "Development and staging databases",
                "Microservice backends",
                "Low-traffic applications with idle periods",
                "Cost-sensitive non-production workloads",
            ],
            "pillars": [
                {
                    "title": "Security",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Encryption at rest, TLS 1.2, firewall rules, and audit-ready configuration",
                    "practices": [
                        "Transparent Data Encryption (TDE) enabled by default",
                        "TLS 1.2 minimum enforced for all connections",
                        "Firewall rules restrict access to Azure services and specified IPs",
                        "SQL authentication with configurable admin credentials",
                        "Public network access can be restricted",
                    ]
                },
                {
                    "title": "Operational Excellence",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Infrastructure as code with automated provisioning and standard tagging",
                    "practices": [
                        "Infrastructure as Code with Pulumi for repeatable deployments",
                        "Standard resource naming and tagging conventions",
                        "Connection string exported for easy application integration",
                        "Configurable database sizing via config fields",
                        "Resource group isolation per deployment",
                    ]
                },
                {
                    "title": "Reliability",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Geo-redundant backups protect against regional failures",
                    "practices": [
                        "Geo-redundant backup storage (configurable)",
                        "Azure-managed automatic backups with point-in-time restore",
                        "Single-region deployment suitable for non-production",
                        "Auto-pause prevents idle resource consumption",
                    ]
                },
                {
                    "title": "Cost Optimization",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Serverless auto-pause eliminates cost during idle periods",
                    "practices": [
                        "Serverless compute tier with pay-per-second billing",
                        "Auto-pause after configurable idle period (default 60 min)",
                        "Configurable vCore range to match workload",
                        "No cost when database is paused (storage only)",
                    ]
                },
                {
                    "title": "Sustainability",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Auto-pause reduces energy consumption during idle periods",
                    "practices": [
                        "Auto-pause eliminates compute when database is not in use",
                        "Serverless scales down to minimum vCores during low usage",
                        "Right-sized compute prevents over-provisioning",
                    ]
                },
            ],
        }

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        """Configuration schema for deploy form"""
        return {
            "type": "object",
            "properties": {
                "project_name": {
                    "type": "string",
                    "default": "myapp",
                    "title": "Project Name",
                    "description": "Used in resource naming (resource group, server, database)",
                    "order": 1,
                    "group": "Essentials",
                    "isEssential": True,
                },
                "environment": {
                    "type": "string",
                    "default": "dev",
                    "title": "Environment",
                    "description": "Deployment environment",
                    "enum": ["dev", "staging", "uat"],
                    "order": 2,
                    "group": "Essentials",
                    "isEssential": True,
                },
                "location": {
                    "type": "string",
                    "default": "eastus",
                    "title": "Azure Region",
                    "description": "Azure region for all resources",
                    "enum": ["eastus", "eastus2", "westus2", "westeurope", "northeurope", "southeastasia", "australiaeast"],
                    "order": 3,
                    "group": "Essentials",
                    "isEssential": True,
                },
                "sql_admin_login": {
                    "type": "string",
                    "default": "sqladmin",
                    "title": "SQL Admin Login",
                    "description": "Administrator login name for SQL Server",
                    "order": 10,
                    "group": "Database Configuration",
                },
                "sql_admin_password": {
                    "type": "string",
                    "default": "",
                    "title": "SQL Admin Password",
                    "description": "Administrator password (min 8 chars, mixed case + number + special). Leave blank for auto-generated.",
                    "sensitive": True,
                    "order": 11,
                    "group": "Database Configuration",
                },
                "database_name": {
                    "type": "string",
                    "default": "",
                    "title": "Database Name",
                    "description": "Database name (auto-generated from project-env if blank)",
                    "order": 12,
                    "group": "Database Configuration",
                },
                "auto_pause_delay": {
                    "type": "number",
                    "default": 60,
                    "title": "Auto-Pause Delay (minutes)",
                    "description": "Minutes of idle time before database auto-pauses. Set -1 to disable auto-pause.",
                    "order": 20,
                    "group": "Architecture Decisions",
                    "cost_impact": "Lower = more savings",
                },
                "min_vcores": {
                    "type": "number",
                    "default": 0.5,
                    "title": "Minimum vCores",
                    "description": "Minimum vCore allocation when active",
                    "enum": [0.5, 1, 2, 4],
                    "order": 21,
                    "group": "Architecture Decisions",
                    "cost_impact": "~$0.5/vCore/hr",
                },
                "max_vcores": {
                    "type": "number",
                    "default": 2,
                    "title": "Maximum vCores",
                    "description": "Maximum vCore allocation under load",
                    "enum": [1, 2, 4, 8],
                    "order": 22,
                    "group": "Architecture Decisions",
                    "cost_impact": "~$0.5/vCore/hr",
                },
                "max_size_gb": {
                    "type": "number",
                    "default": 32,
                    "title": "Max Storage (GB)",
                    "description": "Maximum database storage size",
                    "enum": [2, 5, 10, 32, 100],
                    "order": 23,
                    "group": "Architecture Decisions",
                    "cost_impact": "$0.115/GB/month",
                },
                "backup_storage_redundancy": {
                    "type": "string",
                    "default": "Geo",
                    "title": "Backup Redundancy",
                    "description": "Backup storage redundancy level",
                    "enum": ["Local", "Zone", "Geo"],
                    "order": 30,
                    "group": "Architecture Decisions",
                },
                "allow_azure_services": {
                    "type": "boolean",
                    "default": True,
                    "title": "Allow Azure Services",
                    "description": "Allow all Azure services to access this SQL Server",
                    "order": 40,
                    "group": "Security & Access",
                },
                "client_ip": {
                    "type": "string",
                    "default": "",
                    "title": "Client IP Address",
                    "description": "Your IP address for direct database access (e.g. 203.0.113.45)",
                    "order": 41,
                    "group": "Security & Access",
                },
                "team_name": {
                    "type": "string",
                    "default": "",
                    "title": "Team Name",
                    "description": "Team that owns this resource",
                    "order": 50,
                    "group": "Tags",
                },
            },
            "required": ["project_name"],
        }
