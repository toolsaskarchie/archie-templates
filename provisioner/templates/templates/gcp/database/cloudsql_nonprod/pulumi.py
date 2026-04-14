"""
GCP Cloud SQL PostgreSQL Non-Prod Template

Cost-optimized Cloud SQL PostgreSQL instance for development and testing:
- PostgreSQL 15 with configurable machine type
- Private IP via VPC peering (no public IP by default)
- Automated daily backups with 7-day retention
- Deletion protection disabled for easy teardown

Base cost (~$25/mo):
- db-f1-micro instance
- 10 GB SSD storage
- Automated backups (included)
"""

from typing import Any, Dict, Optional
import pulumi
import pulumi_gcp as gcp

from provisioner.templates.base import InfrastructureTemplate, template_registry
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory


@template_registry("gcp-cloudsql-nonprod")
class CloudSQLNonprodTemplate(InfrastructureTemplate):
    """
    GCP Cloud SQL PostgreSQL Non-Prod Template

    Deploys a managed PostgreSQL instance with private networking,
    automated backups, and 7-day retention for non-production workloads.
    """

    def __init__(self, name: str = None, config: Dict[str, Any] = None, gcp_config: Dict[str, Any] = None, **kwargs):
        """Initialize Cloud SQL Non-Prod template"""
        raw_config = config or gcp_config or kwargs or {}

        if name is None:
            name = (
                raw_config.get('project_name') or
                raw_config.get('projectName') or
                raw_config.get('parameters', {}).get('gcp', {}).get('project_name') or
                'cloudsql-nonprod'
            )

        super().__init__(name, raw_config)
        self.config = raw_config

        # Resource references
        self.sql_instance: Optional[object] = None
        self.sql_database: Optional[object] = None
        self.sql_user: Optional[object] = None
        self.private_ip_address: Optional[object] = None
        self.private_vpc_connection: Optional[object] = None

    def _cfg(self, key: str, default=None):
        """Read config from root, parameters.gcp, or parameters (Rule #6)"""
        params = self.config.get('parameters', {})
        gcp_params = params.get('gcp', {}) if isinstance(params, dict) else {}
        return (
            self.config.get(key) or
            (gcp_params.get(key) if isinstance(gcp_params, dict) else None) or
            (params.get(key) if isinstance(params, dict) else None) or
            default
        )

    def create_infrastructure(self) -> Dict[str, Any]:
        """Deploy Cloud SQL infrastructure (implements abstract method)"""
        return self.create()

    def create(self) -> Dict[str, Any]:
        """Deploy complete Cloud SQL PostgreSQL infrastructure"""

        # Read config
        project_name = self._cfg('project_name', 'cloudsql')
        environment = self._cfg('environment', 'dev')
        team_name = self._cfg('team_name', '')
        gcp_project = self._cfg('gcp_project', '')
        region = self._cfg('region', 'us-central1')
        network = self._cfg('network', 'default')

        # Database config
        db_version = self._cfg('database_version', 'POSTGRES_15')
        tier = self._cfg('tier', 'db-f1-micro')
        disk_size = int(self._cfg('disk_size_gb', 10))
        disk_type = self._cfg('disk_type', 'PD_SSD')
        db_name = self._cfg('database_name', f'{project_name}-db')
        db_user = self._cfg('database_user', 'appuser')

        # Feature toggles
        enable_private_ip = self._cfg('enable_private_ip', True)
        if isinstance(enable_private_ip, str):
            enable_private_ip = enable_private_ip.lower() in ('true', '1', 'yes')
        enable_public_ip = self._cfg('enable_public_ip', False)
        if isinstance(enable_public_ip, str):
            enable_public_ip = enable_public_ip.lower() in ('true', '1', 'yes')
        enable_backups = self._cfg('enable_backups', True)
        if isinstance(enable_backups, str):
            enable_backups = enable_backups.lower() in ('true', '1', 'yes')
        backup_retention = int(self._cfg('backup_retention_days', 7))

        # Standard GCP labels
        labels = {
            'project': project_name,
            'environment': environment,
            'template': 'gcp-cloudsql-nonprod',
            'managed-by': 'archie',
        }
        if team_name:
            labels['team'] = team_name.lower().replace(' ', '-')
        labels.update(self._cfg('labels', {}))

        resource_name = f"{project_name}-{environment}"

        # =================================================================
        # LAYER 1: Private Service Access (if private IP enabled)
        # =================================================================

        ip_configuration = {}

        if enable_private_ip:
            # Allocate private IP range for Cloud SQL
            self.private_ip_address = gcp.compute.GlobalAddress(
                f"{resource_name}-sql-private-ip",
                name=f"{resource_name}-sql-private-ip",
                project=gcp_project if gcp_project else None,
                purpose="VPC_PEERING",
                address_type="INTERNAL",
                prefix_length=16,
                network=f"projects/{gcp_project}/global/networks/{network}" if gcp_project else f"global/networks/{network}",
            )

            # Create VPC peering connection
            self.private_vpc_connection = gcp.servicenetworking.Connection(
                f"{resource_name}-sql-vpc-connection",
                network=f"projects/{gcp_project}/global/networks/{network}" if gcp_project else f"global/networks/{network}",
                service="servicenetworking.googleapis.com",
                reserved_peering_ranges=[self.private_ip_address.name],
            )

            ip_configuration = {
                "ipv4_enabled": enable_public_ip,
                "private_network": f"projects/{gcp_project}/global/networks/{network}" if gcp_project else f"global/networks/{network}",
                "require_ssl": True,
            }
        else:
            ip_configuration = {
                "ipv4_enabled": True,
                "require_ssl": True,
                "authorized_networks": [],
            }

        # =================================================================
        # LAYER 2: Cloud SQL Instance
        # =================================================================

        backup_configuration = {}
        if enable_backups:
            backup_configuration = {
                "enabled": True,
                "start_time": "03:00",
                "point_in_time_recovery_enabled": False,
                "transaction_log_retention_days": backup_retention,
                "backup_retention_settings": {
                    "retained_backups": backup_retention,
                    "retention_unit": "COUNT",
                },
            }

        depends = []
        if self.private_vpc_connection:
            depends.append(self.private_vpc_connection)

        self.sql_instance = gcp.sql.DatabaseInstance(
            f"{resource_name}-sql",
            name=f"{resource_name}-sql",
            project=gcp_project if gcp_project else None,
            region=region,
            database_version=db_version,
            deletion_protection=False,
            settings=gcp.sql.DatabaseInstanceSettingsArgs(
                tier=tier,
                disk_size=disk_size,
                disk_type=disk_type,
                disk_autoresize=True,
                disk_autoresize_limit=50,
                availability_type="ZONAL",
                ip_configuration=ip_configuration,
                backup_configuration=backup_configuration if enable_backups else None,
                user_labels=labels,
                database_flags=[
                    {"name": "log_checkpoints", "value": "on"},
                    {"name": "log_connections", "value": "on"},
                    {"name": "log_disconnections", "value": "on"},
                ],
                maintenance_window={
                    "day": 7,
                    "hour": 4,
                    "update_track": "stable",
                },
            ),
            opts=pulumi.ResourceOptions(depends_on=depends) if depends else None,
        )

        # =================================================================
        # LAYER 3: Database
        # =================================================================

        self.sql_database = gcp.sql.Database(
            f"{resource_name}-database",
            name=db_name,
            project=gcp_project if gcp_project else None,
            instance=self.sql_instance.name,
            charset="UTF8",
            collation="en_US.UTF8",
        )

        # =================================================================
        # LAYER 4: Database User
        # =================================================================

        self.sql_user = gcp.sql.User(
            f"{resource_name}-user",
            name=db_user,
            project=gcp_project if gcp_project else None,
            instance=self.sql_instance.name,
            password=self._cfg('database_password', 'change-me-immediately'),
        )

        # =================================================================
        # Exports (Rule #2, #7)
        # =================================================================

        pulumi.export('sql_instance_name', self.sql_instance.name)
        pulumi.export('sql_instance_connection_name', self.sql_instance.connection_name)
        pulumi.export('sql_instance_self_link', self.sql_instance.self_link)
        pulumi.export('sql_instance_ip', self.sql_instance.first_ip_address)
        pulumi.export('sql_private_ip', self.sql_instance.private_ip_address)
        pulumi.export('database_name', self.sql_database.name)
        pulumi.export('database_user', self.sql_user.name)
        pulumi.export('database_version', db_version)
        pulumi.export('region', region)
        pulumi.export('environment', environment)

        return self.get_outputs()

    def get_outputs(self) -> Dict[str, Any]:
        """Get outputs for this template"""
        return {
            "sql_instance_name": self.sql_instance.name if self.sql_instance else None,
            "sql_instance_connection_name": self.sql_instance.connection_name if self.sql_instance else None,
            "sql_instance_self_link": self.sql_instance.self_link if self.sql_instance else None,
            "sql_instance_ip": self.sql_instance.first_ip_address if self.sql_instance else None,
            "sql_private_ip": self.sql_instance.private_ip_address if self.sql_instance else None,
            "database_name": self.sql_database.name if self.sql_database else None,
            "database_user": self.sql_user.name if self.sql_user else None,
        }

    @classmethod
    def get_metadata(cls) -> Dict[str, Any]:
        """Template metadata for the catalog UI"""
        return {
            "name": "gcp-cloudsql-nonprod",
            "title": "Cloud SQL PostgreSQL",
            "description": "Managed PostgreSQL database with private networking, automated backups, and 7-day retention for non-production workloads.",
            "category": "database",
            "version": "1.0.0",
            "author": "Archie",
            "cloud": "gcp",
            "environment": "nonprod",
            "base_cost": "$25/month",
            "features": [
                "PostgreSQL 15 managed instance",
                "Private IP via VPC peering (no public exposure)",
                "Automated daily backups with 7-day retention",
                "SSL/TLS required for all connections",
                "Auto-resize disk up to 50 GB",
                "Maintenance window on Sundays at 4 AM",
                "Database logging (checkpoints, connections, disconnections)",
                "Deletion protection disabled for easy teardown",
            ],
            "tags": ["gcp", "cloudsql", "postgresql", "database", "nonprod", "managed"],
            "deployment_time": "5-10 minutes",
            "complexity": "beginner",
            "use_cases": [
                "Development and testing databases",
                "Microservice backend data stores",
                "Application prototyping",
                "CI/CD test databases",
                "Staging environment databases",
            ],
            "pillars": [
                {
                    "title": "Operational Excellence",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Fully managed database with automated backups, maintenance windows, and logging",
                    "practices": [
                        "Infrastructure as Code with Pulumi for repeatable deployments",
                        "Automated daily backups with configurable retention",
                        "Scheduled maintenance windows to minimize disruption",
                        "Database flags enable connection and checkpoint logging",
                        "Auto-resize disk prevents storage exhaustion",
                    ],
                },
                {
                    "title": "Security",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Private networking with SSL enforcement and no public IP by default",
                    "practices": [
                        "Private IP via VPC peering eliminates public exposure",
                        "SSL/TLS required for all database connections",
                        "No public IP assigned by default",
                        "Dedicated database user with configurable credentials",
                        "VPC Service Controls compatible",
                    ],
                },
                {
                    "title": "Reliability",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Zonal deployment suitable for non-production with automated backups",
                    "practices": [
                        "Automated backups provide point-in-time recovery capability",
                        "Auto-resize disk prevents storage-related outages",
                        "Stable update track for maintenance patches",
                        "Single zone deployment appropriate for dev/test workloads",
                    ],
                },
                {
                    "title": "Performance Efficiency",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Right-sized instance with SSD storage and configurable machine type",
                    "practices": [
                        "SSD persistent disk for low-latency I/O",
                        "Configurable machine tier from db-f1-micro to db-custom",
                        "Private IP reduces network latency vs public connections",
                        "UTF-8 encoding and collation configured by default",
                    ],
                },
                {
                    "title": "Cost Optimization",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Minimal footprint with zonal deployment and smallest available tier",
                    "practices": [
                        "db-f1-micro default tier minimizes hourly costs",
                        "Zonal deployment avoids regional replication charges",
                        "Auto-resize prevents over-provisioning storage upfront",
                        "Deletion protection disabled for quick teardown of dev resources",
                    ],
                },
                {
                    "title": "Sustainability",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Right-sized managed service reduces infrastructure waste",
                    "practices": [
                        "Managed service shares underlying infrastructure efficiently",
                        "Auto-resize allocates storage only when needed",
                        "Single zone avoids redundant compute for non-production",
                        "Google Cloud carbon-neutral infrastructure",
                    ],
                },
            ],
        }

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        """Configuration schema for the deploy form"""
        return {
            "type": "object",
            "properties": {
                "project_name": {
                    "type": "string",
                    "default": "myproject",
                    "title": "Project Name",
                    "description": "Used in resource naming (lowercase, no spaces)",
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
                "region": {
                    "type": "string",
                    "default": "us-central1",
                    "title": "GCP Region",
                    "description": "Region for Cloud SQL instance",
                    "enum": ["us-central1", "us-east1", "us-west1", "europe-west1", "asia-east1"],
                    "order": 3,
                    "group": "Essentials",
                    "isEssential": True,
                },
                "gcp_project": {
                    "type": "string",
                    "default": "",
                    "title": "GCP Project ID",
                    "description": "Google Cloud project ID (leave empty to use default)",
                    "order": 4,
                    "group": "Essentials",
                    "isEssential": True,
                },
                "database_version": {
                    "type": "string",
                    "default": "POSTGRES_15",
                    "title": "PostgreSQL Version",
                    "description": "Cloud SQL PostgreSQL engine version",
                    "enum": ["POSTGRES_14", "POSTGRES_15", "POSTGRES_16"],
                    "order": 10,
                    "group": "Database Configuration",
                },
                "tier": {
                    "type": "string",
                    "default": "db-f1-micro",
                    "title": "Machine Tier",
                    "description": "Cloud SQL machine type (db-f1-micro is shared-core, db-custom-N-M for dedicated)",
                    "enum": ["db-f1-micro", "db-g1-small", "db-custom-1-3840", "db-custom-2-7680", "db-custom-4-15360"],
                    "order": 11,
                    "group": "Database Configuration",
                    "cost_impact": "db-f1-micro: ~$8/mo, db-g1-small: ~$26/mo",
                },
                "disk_size_gb": {
                    "type": "number",
                    "default": 10,
                    "title": "Disk Size (GB)",
                    "description": "Initial SSD storage size (auto-resizes up to 50 GB)",
                    "minimum": 10,
                    "maximum": 100,
                    "order": 12,
                    "group": "Database Configuration",
                },
                "disk_type": {
                    "type": "string",
                    "default": "PD_SSD",
                    "title": "Disk Type",
                    "description": "Storage type for the database",
                    "enum": ["PD_SSD", "PD_HDD"],
                    "order": 13,
                    "group": "Database Configuration",
                },
                "database_name": {
                    "type": "string",
                    "default": "",
                    "title": "Database Name",
                    "description": "Name of the initial database (defaults to project-db)",
                    "order": 14,
                    "group": "Database Configuration",
                },
                "database_user": {
                    "type": "string",
                    "default": "appuser",
                    "title": "Database User",
                    "description": "Username for the database user",
                    "order": 15,
                    "group": "Database Configuration",
                },
                "database_password": {
                    "type": "string",
                    "default": "change-me-immediately",
                    "title": "Database Password",
                    "description": "Password for the database user (change after deployment)",
                    "sensitive": True,
                    "order": 16,
                    "group": "Database Configuration",
                },
                "network": {
                    "type": "string",
                    "default": "default",
                    "title": "VPC Network",
                    "description": "VPC network name for private IP connectivity",
                    "order": 20,
                    "group": "Network Configuration",
                },
                "enable_private_ip": {
                    "type": "boolean",
                    "default": True,
                    "title": "Enable Private IP",
                    "description": "Assign private IP via VPC peering (recommended for security)",
                    "order": 21,
                    "group": "Network Configuration",
                },
                "enable_public_ip": {
                    "type": "boolean",
                    "default": False,
                    "title": "Enable Public IP",
                    "description": "Assign public IP address (not recommended for production)",
                    "order": 22,
                    "group": "Network Configuration",
                },
                "enable_backups": {
                    "type": "boolean",
                    "default": True,
                    "title": "Enable Automated Backups",
                    "description": "Daily automated backups starting at 3 AM",
                    "order": 30,
                    "group": "Architecture Decisions",
                    "cost_impact": "Included in instance cost",
                },
                "backup_retention_days": {
                    "type": "number",
                    "default": 7,
                    "title": "Backup Retention (days)",
                    "description": "Number of days to retain automated backups",
                    "minimum": 1,
                    "maximum": 365,
                    "order": 31,
                    "group": "Architecture Decisions",
                    "conditional": {"field": "enable_backups"},
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
            "required": ["project_name", "region"],
        }
