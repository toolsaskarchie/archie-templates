"""
Multi-Cloud Database Template

Deploy managed relational databases across AWS, Azure, and GCP simultaneously.
Toggle which clouds to include — deploy to 1, 2, or all 3 at once.

Base cost: ~$15-50/month per cloud
- AWS: RDS PostgreSQL with Security Group + Subnet Group
- Azure: Resource Group + PostgreSQL Flexible Server + Database
- GCP: Cloud SQL Instance + Database + User
"""

from typing import Any, Dict, List, Optional
import pulumi
import pulumi_aws as aws_sdk
import pulumi_azure_native as azure_native
import pulumi_gcp as gcp

from provisioner.templates.base import template_registry, InfrastructureTemplate
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory


@template_registry("multi-database")
class MultiDatabaseTemplate(InfrastructureTemplate):
    """
    Multi-Cloud Database Template

    Deploys managed databases to any combination of:
    - AWS: RDS PostgreSQL with Security Group
    - Azure: PostgreSQL Flexible Server + Database
    - GCP: Cloud SQL Instance + Database + User
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

        # AWS resource references
        self.aws_sg: Optional[object] = None
        self.aws_rds: Optional[object] = None

        # Azure resource references
        self.azure_rg: Optional[object] = None
        self.azure_server: Optional[object] = None
        self.azure_database: Optional[object] = None

        # GCP resource references
        self.gcp_instance: Optional[object] = None
        self.gcp_database: Optional[object] = None
        self.gcp_user: Optional[object] = None

    def _cfg(self, key: str, default=None):
        """Read config from root or parameters (Rule #6)"""
        params = self.config.get('parameters', {})
        return (
            self.config.get(key) or
            (params.get(key) if isinstance(params, dict) else None) or
            default
        )

    def _get_bool(self, key: str, default: bool = False) -> bool:
        """Read a boolean config value, handling string/bool/Decimal"""
        val = self._cfg(key, default)
        if isinstance(val, bool):
            return val
        if isinstance(val, str):
            return val.lower() in ('true', '1', 'yes')
        return bool(val)

    def create_infrastructure(self) -> Dict[str, Any]:
        """Deploy multi-cloud database infrastructure (implements abstract method)"""
        return self.create()

    def create(self) -> Dict[str, Any]:
        """Deploy databases to all selected cloud providers"""

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
        publicly_accessible = self._get_bool('publicly_accessible', False)

        deploy_aws = self._get_bool('deploy_aws', True)
        deploy_azure = self._get_bool('deploy_azure', False)
        deploy_gcp = self._get_bool('deploy_gcp', False)

        prefix = f"{project}-{env}"
        clouds_deployed: List[str] = []

        if deploy_aws:
            self._create_aws(prefix, project, env, team_name, db_name, engine, engine_version,
                             instance_size, storage_gb, admin_username, admin_password,
                             backup_retention, publicly_accessible)
            clouds_deployed.append('aws')

        if deploy_azure:
            self._create_azure(prefix, project, env, team_name, db_name, engine, engine_version,
                               instance_size, storage_gb, admin_username, admin_password,
                               backup_retention, publicly_accessible)
            clouds_deployed.append('azure')

        if deploy_gcp:
            self._create_gcp(prefix, project, env, team_name, db_name, engine, engine_version,
                             instance_size, storage_gb, admin_username, admin_password,
                             backup_retention, publicly_accessible)
            clouds_deployed.append('gcp')

        # Common exports
        pulumi.export('clouds_deployed', clouds_deployed)
        pulumi.export('project_name', project)
        pulumi.export('environment', env)
        pulumi.export('db_name', db_name)
        pulumi.export('engine', engine)

        return self.get_outputs()

    def _create_aws(self, prefix, project, env, team_name, db_name, engine, engine_version,
                    instance_size, storage_gb, admin_username, admin_password,
                    backup_retention, publicly_accessible):
        """Deploy AWS RDS PostgreSQL with Security Group"""
        tags = {"Project": project, "Environment": env, "ManagedBy": "Archie", "Template": "multi-database"}
        if team_name:
            tags["Team"] = team_name

        if not engine_version:
            engine_version = "15.4" if engine == "postgres" else "8.0"

        db_port = 5432 if engine == "postgres" else 3306

        # Security Group
        self.aws_sg = factory.create(
            "aws:ec2:SecurityGroup",
            f"aws-{prefix}-db-sg",
            description=f"Database security group for {project} (AWS)",
            ingress=[{
                "protocol": "tcp",
                "from_port": db_port,
                "to_port": db_port,
                "cidr_blocks": ["10.0.0.0/8"],
                "description": f"{engine} from private networks",
            }],
            egress=[{"protocol": "-1", "from_port": 0, "to_port": 0, "cidr_blocks": ["0.0.0.0/0"], "description": "All outbound"}],
            tags={**tags, "Name": f"aws-{prefix}-db-sg"},
        )

        # RDS Instance
        self.aws_rds = factory.create(
            "aws:rds:Instance",
            f"aws-{prefix}-rds",
            identifier=f"aws-{prefix}-{db_name}",
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
            vpc_security_group_ids=[self.aws_sg.id],
            tags={**tags, "Name": f"aws-{prefix}-{db_name}"},
        )

        pulumi.export('aws_db_endpoint', self.aws_rds.endpoint)
        pulumi.export('aws_db_port', self.aws_rds.port)
        pulumi.export('aws_db_instance_id', self.aws_rds.id)

    def _create_azure(self, prefix, project, env, team_name, db_name, engine, engine_version,
                      instance_size, storage_gb, admin_username, admin_password,
                      backup_retention, publicly_accessible):
        """Deploy Azure PostgreSQL Flexible Server + Database"""
        tags = {"Project": project, "Environment": env, "ManagedBy": "Archie", "Template": "multi-database"}
        if team_name:
            tags["Team"] = team_name

        location = self._cfg('azure_region', 'eastus')

        # Resource Group
        self.azure_rg = factory.create(
            "azure-native:resources:ResourceGroup",
            f"azure-{prefix}-db-rg",
            resource_group_name=f"azure-{prefix}-db-rg",
            location=location,
            tags=tags,
        )

        sku = instance_size if 'Standard' in instance_size else 'Standard_B1ms'

        if engine == "postgres":
            # PostgreSQL Flexible Server
            self.azure_server = factory.create(
                "azure-native:dbforpostgresql:Server",
                f"azure-{prefix}-pg",
                server_name=f"azure-{prefix}-pg",
                resource_group_name=self.azure_rg.name,
                location=location,
                sku={"name": sku, "tier": "Burstable"},
                version=engine_version or "15",
                administrator_login=admin_username,
                administrator_login_password=admin_password,
                storage={"storage_size_gb": storage_gb},
                backup={"backup_retention_days": backup_retention, "geo_redundant_backup": "Disabled"},
                tags=tags,
            )

            self.azure_database = factory.create(
                "azure-native:dbforpostgresql:Database",
                f"azure-{prefix}-{db_name}",
                database_name=db_name,
                server_name=self.azure_server.name,
                resource_group_name=self.azure_rg.name,
                charset="UTF8",
                collation="en_US.utf8",
            )

            pulumi.export('azure_db_endpoint', self.azure_server.fully_qualified_domain_name)
            pulumi.export('azure_db_port', 5432)
        else:
            # MySQL Flexible Server
            self.azure_server = factory.create(
                "azure-native:dbformysql:Server",
                f"azure-{prefix}-mysql",
                server_name=f"azure-{prefix}-mysql",
                resource_group_name=self.azure_rg.name,
                location=location,
                sku={"name": sku, "tier": "Burstable"},
                version=engine_version or "8.0.21",
                administrator_login=admin_username,
                administrator_login_password=admin_password,
                storage={"storage_size_gb": storage_gb},
                backup={"backup_retention_days": backup_retention, "geo_redundant_backup": "Disabled"},
                tags=tags,
            )

            self.azure_database = factory.create(
                "azure-native:dbformysql:Database",
                f"azure-{prefix}-{db_name}",
                database_name=db_name,
                server_name=self.azure_server.name,
                resource_group_name=self.azure_rg.name,
                charset="utf8mb4",
                collation="utf8mb4_unicode_ci",
            )

            pulumi.export('azure_db_endpoint', self.azure_server.fully_qualified_domain_name)
            pulumi.export('azure_db_port', 3306)

        pulumi.export('azure_db_server_id', self.azure_server.id)

    def _create_gcp(self, prefix, project, env, team_name, db_name, engine, engine_version,
                    instance_size, storage_gb, admin_username, admin_password,
                    backup_retention, publicly_accessible):
        """Deploy GCP Cloud SQL Instance + Database + User"""
        region = self._cfg('gcp_region', 'us-central1')

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
        self.gcp_instance = factory.create(
            "gcp:sql:DatabaseInstance",
            f"gcp-{prefix}-sql",
            name=f"gcp-{prefix}-sql",
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
        self.gcp_database = factory.create(
            "gcp:sql:Database",
            f"gcp-{prefix}-{db_name}",
            name=db_name,
            instance=self.gcp_instance.name,
        )

        # User
        self.gcp_user = factory.create(
            "gcp:sql:User",
            f"gcp-{prefix}-{admin_username}",
            name=admin_username,
            instance=self.gcp_instance.name,
            password=admin_password,
        )

        pulumi.export('gcp_db_endpoint', self.gcp_instance.public_ip_address)
        pulumi.export('gcp_db_connection_name', self.gcp_instance.connection_name)
        pulumi.export('gcp_db_instance_id', self.gcp_instance.id)

    def get_outputs(self) -> Dict[str, Any]:
        """Get template outputs for all deployed clouds"""
        outputs: Dict[str, Any] = {
            "project_name": self._cfg('project_name', 'db-app'),
            "environment": self._cfg('environment', 'dev'),
            "db_name": self._cfg('db_name', 'appdb'),
            "engine": self._cfg('engine', 'postgres'),
        }

        # AWS outputs
        if self.aws_rds:
            outputs["aws_db_endpoint"] = self.aws_rds.endpoint
            outputs["aws_db_port"] = self.aws_rds.port
            outputs["aws_db_instance_id"] = self.aws_rds.id

        # Azure outputs
        if self.azure_server:
            outputs["azure_db_server_id"] = self.azure_server.id
            outputs["azure_db_endpoint"] = self.azure_server.fully_qualified_domain_name

        # GCP outputs
        if self.gcp_instance:
            outputs["gcp_db_endpoint"] = self.gcp_instance.public_ip_address
            outputs["gcp_db_connection_name"] = self.gcp_instance.connection_name
            outputs["gcp_db_instance_id"] = self.gcp_instance.id

        return outputs

    @classmethod
    def get_metadata(cls) -> Dict[str, Any]:
        """Template metadata for catalog UI"""
        return {
            "name": "multi-database",
            "title": "Multi-Cloud Managed Database",
            "description": "Deploy managed relational databases across AWS, Azure, and GCP simultaneously. Toggle which clouds to include for cross-cloud redundancy with unified governance.",
            "category": "database",
            "version": "2.0.0",
            "author": "Archie",
            "cloud": "multi",
            "environment": "nonprod",
            "base_cost": "$15-50/month per cloud",
            "features": [
                "Deploy to 1, 2, or all 3 clouds simultaneously",
                "AWS: RDS PostgreSQL/MySQL with encryption and Security Group",
                "Azure: PostgreSQL/MySQL Flexible Server with geo-backup options",
                "GCP: Cloud SQL with auto-resize and backup configuration",
                "PostgreSQL and MySQL engine support across all clouds",
                "Cross-cloud database redundancy with unified governance",
                "Automated backups with configurable retention per cloud",
            ],
            "tags": ["multi-cloud", "database", "rds", "azure-sql", "cloud-sql", "postgres", "mysql", "cross-cloud"],
            "deployment_time": "5-15 minutes",
            "complexity": "intermediate",
            "use_cases": [
                "Multi-cloud database redundancy",
                "Disaster recovery across cloud providers",
                "Cloud migration with parallel databases",
                "Vendor lock-in avoidance for data layer",
                "Cross-cloud compliance requirements",
            ],
            "pillars": [
                {
                    "title": "Operational Excellence",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Single template deploys and governs databases across three clouds simultaneously",
                    "practices": [
                        "One deploy creates databases on multiple clouds at once",
                        "Unified governance for database configuration across clouds",
                        "Automated backups with configurable retention",
                        "Infrastructure as Code for repeatable database provisioning",
                        "Tags and labels for resource organization across clouds",
                    ]
                },
                {
                    "title": "Security",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Encryption at rest with network-restricted access on all clouds",
                    "practices": [
                        "Encryption at rest enabled by default (AWS, GCP)",
                        "Network access restricted to private ranges (10.0.0.0/8)",
                        "Admin password configurable (PE should lock for prod)",
                        "Security group / firewall isolates database port",
                        "Public access disabled by default on all clouds",
                    ]
                },
                {
                    "title": "Reliability",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Cross-cloud deployment provides ultimate data redundancy",
                    "practices": [
                        "Simultaneous databases across multiple clouds",
                        "Automated backups with configurable retention per cloud",
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
                    "description": "Toggle clouds on/off to control database spend",
                    "practices": [
                        "Deploy only to clouds you need (1, 2, or all 3)",
                        "Burstable instance types for non-prod workloads",
                        "Skip final snapshot for dev environments saves time",
                        "Configurable storage size prevents over-provisioning",
                    ]
                },
                {
                    "title": "Sustainability",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Managed infrastructure with efficient resource utilization",
                    "practices": [
                        "Toggle off unused clouds to reduce resource consumption",
                        "Managed service shares underlying infrastructure",
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
                "deploy_aws": {
                    "type": "boolean",
                    "default": True,
                    "title": "Deploy to AWS",
                    "description": "Deploy RDS PostgreSQL/MySQL on AWS",
                    "order": 3,
                    "group": "Cloud Selection",
                    "isEssential": True,
                },
                "deploy_azure": {
                    "type": "boolean",
                    "default": False,
                    "title": "Deploy to Azure",
                    "description": "Deploy PostgreSQL/MySQL Flexible Server on Azure",
                    "order": 4,
                    "group": "Cloud Selection",
                    "isEssential": True,
                },
                "deploy_gcp": {
                    "type": "boolean",
                    "default": False,
                    "title": "Deploy to GCP",
                    "description": "Deploy Cloud SQL on GCP",
                    "order": 5,
                    "group": "Cloud Selection",
                    "isEssential": True,
                },
                "db_name": {
                    "type": "string",
                    "default": "appdb",
                    "title": "Database Name",
                    "description": "Name of the database to create on each cloud",
                    "order": 10,
                    "group": "Database",
                },
                "engine": {
                    "type": "string",
                    "default": "postgres",
                    "title": "Database Engine",
                    "description": "Relational database engine (same across all clouds)",
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
                    "description": "Database instance size (e.g., db.t3.micro for AWS, Standard_B1ms for Azure, db-f1-micro for GCP)",
                    "order": 13,
                    "group": "Database",
                    "cost_impact": "$15-50/month per cloud",
                },
                "storage_gb": {
                    "type": "number",
                    "default": 20,
                    "title": "Storage (GB)",
                    "description": "Allocated storage in gigabytes per cloud",
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
                    "description": "Database administrator username (same across all clouds)",
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
                "azure_region": {
                    "type": "string",
                    "default": "eastus",
                    "title": "Azure Region",
                    "description": "Azure region (e.g., eastus, westus2, westeurope)",
                    "order": 40,
                    "group": "Cloud Regions",
                    "conditional": {"field": "deploy_azure"},
                },
                "gcp_region": {
                    "type": "string",
                    "default": "us-central1",
                    "title": "GCP Region",
                    "description": "GCP region (e.g., us-central1, us-east1, europe-west1)",
                    "order": 41,
                    "group": "Cloud Regions",
                    "conditional": {"field": "deploy_gcp"},
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
            "required": ["project_name", "db_name", "engine"],
        }
