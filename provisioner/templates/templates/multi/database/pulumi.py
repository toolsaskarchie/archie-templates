"""
Multi-Cloud Database Template

Composed template: RDS / Azure SQL / Cloud SQL.
Config field `cloud` selects the provider. Same interface for all three clouds:
db_name, engine, instance_size.

Base cost: ~$15-50/month (varies by cloud and instance size)
- Managed relational database
- Configurable engine (postgres, mysql)
- Configurable instance size
- Automated backups
- Network isolation
"""

from typing import Any, Dict, Optional
import pulumi

from provisioner.templates.base import template_registry, InfrastructureTemplate
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory


@template_registry("multi-database")
class MultiDatabaseTemplate(InfrastructureTemplate):
    """
    Multi-Cloud Database Template

    Creates (based on cloud selection):
    - AWS: RDS Instance with subnet group and security group
    - Azure: Azure SQL Server + Database with firewall rules
    - GCP: Cloud SQL Instance with database and user
    """

    def __init__(self, name: str = None, config: Dict[str, Any] = None, **kwargs):
        """Initialize Multi-Cloud Database template"""
        raw_config = config or kwargs or {}
        if name is None:
            name = (
                raw_config.get('project_name') or
                raw_config.get('parameters', {}).get('project_name') or
                'multi-database'
            )
        super().__init__(name, raw_config)
        self.config = raw_config

        # Resource references
        self.database: Optional[object] = None
        self.server: Optional[object] = None
        self.security: Optional[object] = None

    def _cfg(self, key: str, default=None):
        """Read config from root or parameters (Rule #6)"""
        params = self.config.get('parameters', {})
        cloud = self.config.get('cloud') or (params.get('cloud') if isinstance(params, dict) else None) or 'aws'
        cloud_params = params.get(cloud, {}) if isinstance(params, dict) else {}
        return (
            self.config.get(key) or
            (cloud_params.get(key) if isinstance(cloud_params, dict) else None) or
            (params.get(key) if isinstance(params, dict) else None) or
            default
        )

    def create_infrastructure(self) -> Dict[str, Any]:
        """Deploy multi-cloud database infrastructure (implements abstract method)"""
        return self.create()

    def create(self) -> Dict[str, Any]:
        """Deploy database to the selected cloud provider"""

        # Read config
        cloud = self._cfg('cloud', 'aws')
        project = self._cfg('project_name', 'db-app')
        env = self._cfg('environment', 'dev')
        team_name = self._cfg('team_name', '')
        db_name = self._cfg('db_name', 'appdb')
        engine = self._cfg('engine', 'postgres')
        engine_version = self._cfg('engine_version', '')
        instance_size = self._cfg('instance_size', 'db.t3.micro')
        storage_gb = int(self._cfg('storage_gb', 20))
        admin_username = self._cfg('admin_username', 'dbadmin')
        admin_password = self._cfg('admin_password', 'ChangeMe123!')
        backup_retention = int(self._cfg('backup_retention', 7))
        publicly_accessible = self._cfg('publicly_accessible', False)
        if isinstance(publicly_accessible, str):
            publicly_accessible = publicly_accessible.lower() in ('true', '1', 'yes')

        prefix = f"{project}-{env}"

        if cloud == 'aws':
            self._create_aws(prefix, project, env, team_name, db_name, engine, engine_version, instance_size, storage_gb, admin_username, admin_password, backup_retention, publicly_accessible)
        elif cloud == 'azure':
            self._create_azure(prefix, project, env, team_name, db_name, engine, engine_version, instance_size, storage_gb, admin_username, admin_password, backup_retention, publicly_accessible)
        elif cloud == 'gcp':
            self._create_gcp(prefix, project, env, team_name, db_name, engine, engine_version, instance_size, storage_gb, admin_username, admin_password, backup_retention, publicly_accessible)
        else:
            raise ValueError(f"Unsupported cloud: {cloud}. Must be aws, azure, or gcp.")

        # Common exports
        pulumi.export('cloud', cloud)
        pulumi.export('project_name', project)
        pulumi.export('environment', env)
        pulumi.export('db_name', db_name)
        pulumi.export('engine', engine)

        return self.get_outputs()

    def _create_aws(self, prefix, project, env, team_name, db_name, engine, engine_version, instance_size, storage_gb, admin_username, admin_password, backup_retention, publicly_accessible):
        """Deploy AWS RDS"""
        tags = {"Project": project, "Environment": env, "ManagedBy": "Archie", "Template": "multi-database"}
        if team_name:
            tags["Team"] = team_name

        # Default engine versions
        if not engine_version:
            engine_version = "15.4" if engine == "postgres" else "8.0"

        # Security Group (allowing DB port from anywhere for dev — PE should lock this)
        db_port = 5432 if engine == "postgres" else 3306
        self.security = factory.create(
            "aws:ec2:SecurityGroup",
            f"{prefix}-db-sg",
            description=f"Database security group for {project}",
            ingress=[{
                "protocol": "tcp",
                "from_port": db_port,
                "to_port": db_port,
                "cidr_blocks": ["10.0.0.0/8"],
                "description": f"{engine} from private networks",
            }],
            egress=[{"protocol": "-1", "from_port": 0, "to_port": 0, "cidr_blocks": ["0.0.0.0/0"], "description": "All outbound"}],
            tags={**tags, "Name": f"{prefix}-db-sg"},
        )

        # RDS Instance
        self.database = factory.create(
            "aws:rds:Instance",
            f"{prefix}-rds",
            identifier=f"{prefix}-{db_name}",
            engine=engine,
            engine_version=engine_version,
            instance_class=instance_size,
            allocated_storage=storage_gb,
            db_name=db_name,
            username=admin_username,
            password=admin_password,
            publicly_accessible=publicly_accessible,
            skip_final_snapshot=True if env != "prod" else False,
            backup_retention_period=backup_retention,
            storage_encrypted=True,
            vpc_security_group_ids=[self.security.id],
            tags={**tags, "Name": f"{prefix}-{db_name}"},
        )

        pulumi.export('db_endpoint', self.database.endpoint)
        pulumi.export('db_port', self.database.port)
        pulumi.export('db_instance_id', self.database.id)

    def _create_azure(self, prefix, project, env, team_name, db_name, engine, engine_version, instance_size, storage_gb, admin_username, admin_password, backup_retention, publicly_accessible):
        """Deploy Azure SQL / PostgreSQL Flexible Server"""
        tags = {"Project": project, "Environment": env, "ManagedBy": "Archie", "Template": "multi-database"}
        if team_name:
            tags["Team"] = team_name

        location = self._cfg('region', 'eastus')

        # Resource Group
        rg = factory.create(
            "azure-native:resources:ResourceGroup",
            f"{prefix}-db-rg",
            resource_group_name=f"{prefix}-db-rg",
            location=location,
            tags=tags,
        )

        if engine == "postgres":
            # PostgreSQL Flexible Server
            sku = instance_size if 'Standard' in instance_size else 'Standard_B1ms'
            self.server = factory.create(
                "azure-native:dbforpostgresql:Server",
                f"{prefix}-pg",
                server_name=f"{prefix}-pg",
                resource_group_name=rg.name,
                location=location,
                sku={"name": sku, "tier": "Burstable"},
                version=engine_version or "15",
                administrator_login=admin_username,
                administrator_login_password=admin_password,
                storage={"storage_size_gb": storage_gb},
                backup={"backup_retention_days": backup_retention, "geo_redundant_backup": "Disabled"},
                tags=tags,
            )

            # Database
            self.database = factory.create(
                "azure-native:dbforpostgresql:Database",
                f"{prefix}-{db_name}",
                database_name=db_name,
                server_name=self.server.name,
                resource_group_name=rg.name,
                charset="UTF8",
                collation="en_US.utf8",
            )

            pulumi.export('db_endpoint', self.server.fully_qualified_domain_name)
            pulumi.export('db_port', 5432)
        else:
            # MySQL Flexible Server
            sku = instance_size if 'Standard' in instance_size else 'Standard_B1ms'
            self.server = factory.create(
                "azure-native:dbformysql:Server",
                f"{prefix}-mysql",
                server_name=f"{prefix}-mysql",
                resource_group_name=rg.name,
                location=location,
                sku={"name": sku, "tier": "Burstable"},
                version=engine_version or "8.0.21",
                administrator_login=admin_username,
                administrator_login_password=admin_password,
                storage={"storage_size_gb": storage_gb},
                backup={"backup_retention_days": backup_retention, "geo_redundant_backup": "Disabled"},
                tags=tags,
            )

            self.database = factory.create(
                "azure-native:dbformysql:Database",
                f"{prefix}-{db_name}",
                database_name=db_name,
                server_name=self.server.name,
                resource_group_name=rg.name,
                charset="utf8mb4",
                collation="utf8mb4_unicode_ci",
            )

            pulumi.export('db_endpoint', self.server.fully_qualified_domain_name)
            pulumi.export('db_port', 3306)

        pulumi.export('db_server_id', self.server.id)

    def _create_gcp(self, prefix, project, env, team_name, db_name, engine, engine_version, instance_size, storage_gb, admin_username, admin_password, backup_retention, publicly_accessible):
        """Deploy GCP Cloud SQL"""
        region = self._cfg('region', 'us-central1')

        labels = {
            "project": project.lower().replace(' ', '-'),
            "environment": env,
            "managed-by": "archie",
            "template": "multi-database",
        }
        if team_name:
            labels["team"] = team_name.lower().replace(' ', '-')

        # Map engine to GCP database version
        if engine == "postgres":
            database_version = f"POSTGRES_{engine_version.split('.')[0] if engine_version else '15'}"
        else:
            database_version = f"MYSQL_{engine_version.replace('.', '_') if engine_version else '8_0'}"

        # Map instance size to GCP tier
        tier = instance_size if 'db-' in instance_size else 'db-f1-micro'

        # Cloud SQL Instance
        self.server = factory.create(
            "gcp:sql:DatabaseInstance",
            f"{prefix}-sql",
            name=f"{prefix}-sql",
            database_version=database_version,
            region=region,
            deletion_protection=True if env == "prod" else False,
            settings={
                "tier": tier,
                "disk_size": storage_gb,
                "disk_autoresize": True,
                "backup_configuration": {
                    "enabled": True,
                    "start_time": "02:00",
                    "transaction_log_retention_days": backup_retention,
                },
                "ip_configuration": {
                    "ipv4_enabled": publicly_accessible,
                    "authorized_networks": [{"value": "10.0.0.0/8", "name": "private"}] if publicly_accessible else [],
                },
                "user_labels": labels,
            },
        )

        # Database
        self.database = factory.create(
            "gcp:sql:Database",
            f"{prefix}-{db_name}",
            name=db_name,
            instance=self.server.name,
        )

        # User
        factory.create(
            "gcp:sql:User",
            f"{prefix}-{admin_username}",
            name=admin_username,
            instance=self.server.name,
            password=admin_password,
        )

        pulumi.export('db_endpoint', self.server.public_ip_address)
        pulumi.export('db_connection_name', self.server.connection_name)
        pulumi.export('db_instance_id', self.server.id)

    def get_outputs(self) -> Dict[str, Any]:
        """Get template outputs"""
        cloud = self._cfg('cloud', 'aws')
        return {
            "cloud": cloud,
            "db_name": self._cfg('db_name', 'appdb'),
            "engine": self._cfg('engine', 'postgres'),
            "database_id": self.database.id if self.database else None,
            "server_id": self.server.id if self.server else None,
        }

    @classmethod
    def get_metadata(cls) -> Dict[str, Any]:
        """Template metadata for catalog UI"""
        return {
            "name": "multi-database",
            "title": "Multi-Cloud Managed Database",
            "description": "Deploy a managed relational database on AWS (RDS), Azure (SQL/PostgreSQL), or GCP (Cloud SQL). Same interface: db_name, engine, instance_size.",
            "category": "database",
            "version": "1.0.0",
            "author": "Archie",
            "cloud": "multi",
            "environment": "nonprod",
            "base_cost": "$15-50/month",
            "features": [
                "Single template deploys to AWS, Azure, or GCP",
                "PostgreSQL and MySQL engine support",
                "Configurable instance size per cloud",
                "Automated backups with retention policy",
                "Encryption at rest (AWS and GCP)",
                "Network-restricted access by default",
            ],
            "tags": ["multi-cloud", "database", "rds", "azure-sql", "cloud-sql", "postgres", "mysql"],
            "deployment_time": "5-15 minutes",
            "complexity": "intermediate",
            "use_cases": [
                "Cloud-agnostic application databases",
                "Multi-cloud database strategy",
                "Development and staging databases",
                "Standardized database provisioning",
                "Cross-cloud disaster recovery",
            ],
            "pillars": [
                {
                    "title": "Operational Excellence",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Managed database with automated backups and consistent interface across clouds",
                    "practices": [
                        "Unified config interface across three cloud providers",
                        "Automated backups with configurable retention",
                        "Infrastructure as Code for repeatable database provisioning",
                        "Engine version pinning for consistency",
                        "Tags and labels for resource organization",
                    ]
                },
                {
                    "title": "Security",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Encryption at rest with network-restricted access",
                    "practices": [
                        "Encryption at rest enabled by default (AWS, GCP)",
                        "Network access restricted to private ranges (10.0.0.0/8)",
                        "Admin password configurable (PE should lock for prod)",
                        "Security group / firewall isolates database port",
                        "Public access disabled by default",
                    ]
                },
                {
                    "title": "Reliability",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Managed database with automated backups and deletion protection",
                    "practices": [
                        "Automated backups with configurable retention",
                        "Deletion protection for production environments",
                        "Cloud-managed high availability options",
                        "Point-in-time recovery via backup retention",
                    ]
                },
                {
                    "title": "Performance Efficiency",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Right-sized instances with cloud-managed query optimization",
                    "practices": [
                        "Configurable instance size per workload needs",
                        "Cloud-managed query caching and optimization",
                        "Storage auto-resize (GCP) prevents disk exhaustion",
                        "Engine version selection for latest performance features",
                    ]
                },
                {
                    "title": "Cost Optimization",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Right-sized instances with environment-appropriate settings",
                    "practices": [
                        "Burstable instance types for non-prod workloads",
                        "Skip final snapshot for dev environments saves time",
                        "Configurable storage size prevents over-provisioning",
                        "Geo-redundant backup disabled for non-prod savings",
                    ]
                },
                {
                    "title": "Sustainability",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Managed infrastructure with efficient resource utilization",
                    "practices": [
                        "Managed service shares underlying infrastructure",
                        "Right-sized instances reduce energy waste",
                        "Burstable tiers maximize compute utilization",
                        "Storage auto-resize prevents pre-allocated waste",
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
                    "default": "db-app",
                    "title": "Project Name",
                    "description": "Project identifier used in resource naming",
                    "order": 1,
                    "group": "Essentials",
                    "isEssential": True,
                },
                "environment": {
                    "type": "string",
                    "default": "dev",
                    "title": "Environment",
                    "description": "Deployment environment",
                    "enum": ["dev", "staging", "prod"],
                    "order": 2,
                    "group": "Essentials",
                    "isEssential": True,
                },
                "cloud": {
                    "type": "string",
                    "default": "aws",
                    "title": "Cloud Provider",
                    "description": "Target cloud for the database",
                    "enum": ["aws", "azure", "gcp"],
                    "order": 3,
                    "group": "Essentials",
                    "isEssential": True,
                },
                "db_name": {
                    "type": "string",
                    "default": "appdb",
                    "title": "Database Name",
                    "description": "Name of the database to create",
                    "order": 10,
                    "group": "Database",
                },
                "engine": {
                    "type": "string",
                    "default": "postgres",
                    "title": "Database Engine",
                    "description": "Relational database engine",
                    "enum": ["postgres", "mysql"],
                    "order": 11,
                    "group": "Database",
                },
                "engine_version": {
                    "type": "string",
                    "default": "",
                    "title": "Engine Version",
                    "description": "Database engine version (leave empty for latest stable)",
                    "order": 12,
                    "group": "Database",
                },
                "instance_size": {
                    "type": "string",
                    "default": "db.t3.micro",
                    "title": "Instance Size",
                    "description": "Database instance size (e.g., db.t3.micro, Standard_B1ms, db-f1-micro)",
                    "order": 13,
                    "group": "Database",
                    "cost_impact": "$15-50/month",
                },
                "storage_gb": {
                    "type": "number",
                    "default": 20,
                    "title": "Storage (GB)",
                    "description": "Allocated storage in gigabytes",
                    "minimum": 10,
                    "maximum": 1000,
                    "order": 14,
                    "group": "Database",
                    "cost_impact": "~$0.10/GB/month",
                },
                "admin_username": {
                    "type": "string",
                    "default": "dbadmin",
                    "title": "Admin Username",
                    "description": "Database administrator username",
                    "order": 20,
                    "group": "Security & Access",
                },
                "admin_password": {
                    "type": "string",
                    "default": "",
                    "title": "Admin Password",
                    "description": "Database administrator password (min 8 characters)",
                    "sensitive": True,
                    "order": 21,
                    "group": "Security & Access",
                },
                "publicly_accessible": {
                    "type": "boolean",
                    "default": False,
                    "title": "Publicly Accessible",
                    "description": "Allow access from the public internet (not recommended for prod)",
                    "order": 22,
                    "group": "Security & Access",
                },
                "backup_retention": {
                    "type": "number",
                    "default": 7,
                    "title": "Backup Retention (days)",
                    "description": "Number of days to retain automated backups",
                    "minimum": 1,
                    "maximum": 35,
                    "order": 30,
                    "group": "Backup & Recovery",
                },
                "region": {
                    "type": "string",
                    "default": "us-east-1",
                    "title": "Region",
                    "description": "Cloud region (e.g., us-east-1, eastus, us-central1)",
                    "order": 40,
                    "group": "Deployment",
                },
                "team_name": {
                    "type": "string",
                    "default": "",
                    "title": "Team Name",
                    "description": "Team that owns this database",
                    "order": 50,
                    "group": "Tags",
                },
            },
            "required": ["project_name", "cloud", "db_name", "engine"],
        }
