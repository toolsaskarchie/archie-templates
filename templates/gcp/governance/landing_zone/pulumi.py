"""
GCP Organization Landing Zone

Enterprise-grade multi-project governance architecture for Google Cloud Platform.

Core components:
- Folder hierarchy: Organization -> Folders (Shared Services, Production, Non-Production, Sandbox)
- Project Factory: create projects within folders with standard labels and enabled APIs
- Organization Policies: Restrict VM External IPs, Public Cloud SQL, Uniform Bucket Access, Shared VPC
- VPC Service Controls (optional): access perimeter around sensitive projects
- Cloud Logging: organization sink -> BigQuery dataset (or Cloud Storage bucket) for audit logs
- Cloud Monitoring: notification channels (email), alert policies for budget
- Budget on Billing Account with threshold alerts (50%, 80%, 100%)
- Essential APIs enabled on each project: compute, container, sql, storage, monitoring, logging
- IAM: org-level roles (Org Admin, Billing Admin, Security Admin, Network Admin)

Folder Structure:
  Organization
  +-- Shared Services   (logging, monitoring, networking hub)
  +-- Production        (production workloads)
  +-- Non-Production    (dev, staging, testing)
  +-- Sandbox           (experimentation, playground)
"""

from typing import Any, Dict, List, Optional
import json
import pulumi
import pulumi_gcp as gcp

from provisioner.templates.base import InfrastructureTemplate, template_registry
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory
from provisioner.utils.gcp.labels import get_standard_labels


@template_registry("gcp-landing-zone")
class GCPLandingZoneTemplate(InfrastructureTemplate):
    """
    GCP Organization Landing Zone -- Folder hierarchy, Org Policies,
    Logging, Monitoring, Budgets, IAM, and optional VPC Service Controls.
    """

    def __init__(self, name: str = None, config: Dict[str, Any] = None, gcp_config: Dict[str, Any] = None, **kwargs):
        raw_config = config or gcp_config or kwargs or {}

        if name is None:
            name = (
                raw_config.get('project_name') or
                raw_config.get('projectName') or
                raw_config.get('parameters', {}).get('gcp', {}).get('project_name') or
                'landing-zone'
            )

        super().__init__(name, raw_config)
        self.config = raw_config

        # Resource references
        self.folders: Dict[str, object] = {}
        self.projects: Dict[str, object] = {}
        self.org_policies: Dict[str, object] = {}
        self.log_sink: Optional[object] = None
        self.log_dataset: Optional[object] = None
        self.log_bucket_storage: Optional[object] = None
        self.budget: Optional[object] = None
        self.notification_channel: Optional[object] = None
        self.service_perimeter: Optional[object] = None

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

    def _get_bool(self, key: str, default: bool = False) -> bool:
        """Read boolean config value handling string/bool/Decimal from DynamoDB"""
        val = self._cfg(key, default)
        if isinstance(val, bool):
            return val
        if isinstance(val, str):
            return val.lower() in ('true', '1', 'yes')
        return bool(val)

    def create_infrastructure(self) -> Dict[str, Any]:
        return self.create()

    def create(self) -> Dict[str, Any]:
        project_name = self._cfg('project_name', 'my-org')
        environment = self._cfg('environment', 'foundation')
        team_name = self._cfg('team_name', '')
        org_id = self._cfg('org_id', '')
        billing_account_id = self._cfg('billing_account_id', '')
        folder_names_raw = self._cfg('folder_names', 'shared,production,nonprod,sandbox')
        folder_names = [f.strip() for f in folder_names_raw.split(',')]
        create_projects = self._get_bool('create_projects', False)
        project_prefix = self._cfg('project_prefix', project_name)
        budget_amount = int(self._cfg('budget_amount', 10000))
        budget_contact_emails_raw = self._cfg('budget_contact_emails', '')
        budget_contact_emails = [e.strip() for e in budget_contact_emails_raw.split(',') if e.strip()] if budget_contact_emails_raw else []
        allowed_regions_raw = self._cfg('allowed_regions', 'us-central1,us-east1,europe-west1')
        allowed_regions = [r.strip() for r in allowed_regions_raw.split(',')]
        enable_vpc_service_controls = self._get_bool('enable_vpc_service_controls', False)
        log_sink_destination = self._cfg('log_sink_destination', 'bigquery')

        # Standard labels
        labels = get_standard_labels(
            project=project_name,
            environment=environment,
        )
        if team_name:
            labels['team'] = team_name.lower().replace('_', '-').replace(' ', '-')
        labels.update(self._cfg('labels', {}))

        # Essential APIs to enable on each project
        essential_apis = [
            'compute.googleapis.com',
            'container.googleapis.com',
            'sqladmin.googleapis.com',
            'storage.googleapis.com',
            'monitoring.googleapis.com',
            'logging.googleapis.com',
        ]

        # =================================================================
        # LAYER 1: Folder Hierarchy
        # =================================================================
        print("[LANDING ZONE] Creating folder hierarchy...")

        folder_display_names = {
            'shared': 'Shared Services',
            'production': 'Production',
            'nonprod': 'Non-Production',
            'sandbox': 'Sandbox',
        }

        for folder_key in folder_names:
            display_name = folder_display_names.get(folder_key, folder_key.replace('-', ' ').title())
            self.folders[folder_key] = factory.create(
                "gcp:organizations:Folder",
                f"folder-{folder_key}-{project_name}",
                display_name=display_name,
                parent=f"organizations/{org_id}",
            )

        # =================================================================
        # LAYER 2: Project Factory (Optional)
        # =================================================================
        if create_projects:
            print("[LANDING ZONE] Creating projects in each folder...")

            for folder_key in folder_names:
                proj_id = f"{project_prefix}-{folder_key}"
                proj_labels = {**labels, "folder": folder_key}

                self.projects[folder_key] = factory.create(
                    "gcp:organizations:Project",
                    f"project-{folder_key}-{project_name}",
                    name=proj_id,
                    project_id=proj_id,
                    folder_id=self.folders[folder_key].name,
                    billing_account=billing_account_id,
                    labels=proj_labels,
                    auto_create_network=False,
                )

                # Enable essential APIs on each project
                for api in essential_apis:
                    api_short = api.split('.')[0]
                    factory.create(
                        "gcp:projects:Service",
                        f"api-{folder_key}-{api_short}-{project_name}",
                        project=self.projects[folder_key].project_id,
                        service=api,
                        disable_on_destroy=False,
                        opts=pulumi.ResourceOptions(depends_on=[self.projects[folder_key]]),
                    )

        # =================================================================
        # LAYER 3: Organization Policies
        # =================================================================
        print("[LANDING ZONE] Applying organization policies...")

        # Policy 1: Restrict VM External IPs
        self.org_policies["restrict-vm-external-ip"] = factory.create(
            "gcp:orgpolicy:Policy",
            f"orgpolicy-restrict-vm-ext-ip-{project_name}",
            name=f"organizations/{org_id}/policies/compute.vmExternalIpAccess",
            parent=f"organizations/{org_id}",
            spec=gcp.orgpolicy.PolicySpecArgs(
                rules=[gcp.orgpolicy.PolicySpecRuleArgs(
                    enforce="TRUE",
                )],
            ),
        )

        # Policy 2: Restrict Public Cloud SQL
        self.org_policies["restrict-public-cloudsql"] = factory.create(
            "gcp:orgpolicy:Policy",
            f"orgpolicy-restrict-public-sql-{project_name}",
            name=f"organizations/{org_id}/policies/sql.restrictPublicIp",
            parent=f"organizations/{org_id}",
            spec=gcp.orgpolicy.PolicySpecArgs(
                rules=[gcp.orgpolicy.PolicySpecRuleArgs(
                    enforce="TRUE",
                )],
            ),
        )

        # Policy 3: Enforce Uniform Bucket-Level Access
        self.org_policies["uniform-bucket-access"] = factory.create(
            "gcp:orgpolicy:Policy",
            f"orgpolicy-uniform-bucket-{project_name}",
            name=f"organizations/{org_id}/policies/storage.uniformBucketLevelAccess",
            parent=f"organizations/{org_id}",
            spec=gcp.orgpolicy.PolicySpecArgs(
                rules=[gcp.orgpolicy.PolicySpecRuleArgs(
                    enforce="TRUE",
                )],
            ),
        )

        # Policy 4: Restrict Shared VPC Host Projects
        self.org_policies["restrict-shared-vpc"] = factory.create(
            "gcp:orgpolicy:Policy",
            f"orgpolicy-restrict-shared-vpc-{project_name}",
            name=f"organizations/{org_id}/policies/compute.restrictSharedVpcHostProjects",
            parent=f"organizations/{org_id}",
            spec=gcp.orgpolicy.PolicySpecArgs(
                rules=[gcp.orgpolicy.PolicySpecRuleArgs(
                    enforce="TRUE",
                )],
            ),
        )

        # Policy 5: Restrict allowed regions
        self.org_policies["restrict-regions"] = factory.create(
            "gcp:orgpolicy:Policy",
            f"orgpolicy-restrict-regions-{project_name}",
            name=f"organizations/{org_id}/policies/gcp.resourceLocations",
            parent=f"organizations/{org_id}",
            spec=gcp.orgpolicy.PolicySpecArgs(
                rules=[gcp.orgpolicy.PolicySpecRuleArgs(
                    values=gcp.orgpolicy.PolicySpecRuleValuesArgs(
                        allowed_values=[f"in:{r}" for r in allowed_regions],
                    ),
                )],
            ),
        )

        # =================================================================
        # LAYER 4: Cloud Logging -- Org Sink
        # =================================================================
        print("[LANDING ZONE] Creating organization audit log sink...")

        if log_sink_destination == 'bigquery':
            # BigQuery dataset for audit logs
            self.log_dataset = factory.create(
                "gcp:bigquery:Dataset",
                f"bq-audit-logs-{project_name}",
                dataset_id=f"audit_logs_{project_name.replace('-', '_')}",
                friendly_name=f"Audit Logs - {project_name}",
                description="Organization-wide audit logs from Cloud Logging",
                location="US",
                default_table_expiration_ms=365 * 24 * 60 * 60 * 1000,
                labels={**labels, "purpose": "audit-logs"},
            )

            sink_destination = self.log_dataset.id.apply(
                lambda ds_id: f"bigquery.googleapis.com/{ds_id}"
            )
        else:
            # Cloud Storage bucket for audit logs
            bucket_name = f"archie-audit-logs-{project_name}"
            self.log_bucket_storage = factory.create(
                "gcp:storage:Bucket",
                f"gcs-audit-logs-{project_name}",
                name=bucket_name,
                location="US",
                force_destroy=False,
                uniform_bucket_level_access=True,
                labels={**labels, "purpose": "audit-logs"},
                lifecycle_rules=[gcp.storage.BucketLifecycleRuleArgs(
                    action=gcp.storage.BucketLifecycleRuleActionArgs(
                        type="SetStorageClass",
                        storage_class="COLDLINE",
                    ),
                    condition=gcp.storage.BucketLifecycleRuleConditionArgs(
                        age=90,
                    ),
                ), gcp.storage.BucketLifecycleRuleArgs(
                    action=gcp.storage.BucketLifecycleRuleActionArgs(
                        type="Delete",
                    ),
                    condition=gcp.storage.BucketLifecycleRuleConditionArgs(
                        age=365,
                    ),
                )],
            )

            sink_destination = self.log_bucket_storage.id.apply(
                lambda b_id: f"storage.googleapis.com/{b_id}"
            )

        # Organization log sink
        self.log_sink = factory.create(
            "gcp:logging:OrganizationSink",
            f"logsink-org-{project_name}",
            org_id=org_id,
            name=f"archie-audit-sink-{project_name}",
            destination=sink_destination,
            filter='logName:"cloudaudit.googleapis.com"',
            include_children=True,
        )

        # =================================================================
        # LAYER 5: Cloud Monitoring -- Notification Channels + Alert Policies
        # =================================================================
        print("[LANDING ZONE] Creating monitoring notification channels...")

        notification_channel_ids = []
        for idx, email in enumerate(budget_contact_emails):
            channel = factory.create(
                "gcp:monitoring:NotificationChannel",
                f"notify-email-{idx}-{project_name}",
                display_name=f"Budget Alert - {email}",
                type="email",
                labels={"email_address": email},
            )
            notification_channel_ids.append(channel.id)

        # Budget alert policy (monitoring alert for high spend)
        if notification_channel_ids:
            self.notification_channel = factory.create(
                "gcp:monitoring:AlertPolicy",
                f"alert-budget-{project_name}",
                display_name=f"Budget Alert - {project_name}",
                combiner="OR",
                notification_channels=notification_channel_ids,
                conditions=[gcp.monitoring.AlertPolicyConditionArgs(
                    display_name="Monthly budget threshold exceeded",
                    condition_threshold=gcp.monitoring.AlertPolicyConditionConditionThresholdArgs(
                        filter='metric.type="billing/budget/utilization"',
                        comparison="COMPARISON_GT",
                        threshold_value=0.8,
                        duration="0s",
                    ),
                )],
            )

        # =================================================================
        # LAYER 6: Budget on Billing Account
        # =================================================================
        print(f"[LANDING ZONE] Creating budget alert (${budget_amount}/month)...")

        self.budget = factory.create(
            "gcp:billing:Budget",
            f"budget-org-{project_name}",
            billing_account=billing_account_id,
            display_name=f"archie-budget-{project_name}",
            amount=gcp.billing.BudgetAmountArgs(
                specified_amount=gcp.billing.BudgetAmountSpecifiedAmountArgs(
                    currency_code="USD",
                    units=str(budget_amount),
                ),
            ),
            threshold_rules=[
                gcp.billing.BudgetThresholdRuleArgs(
                    threshold_percent=0.5,
                    spend_basis="CURRENT_SPEND",
                ),
                gcp.billing.BudgetThresholdRuleArgs(
                    threshold_percent=0.8,
                    spend_basis="CURRENT_SPEND",
                ),
                gcp.billing.BudgetThresholdRuleArgs(
                    threshold_percent=1.0,
                    spend_basis="CURRENT_SPEND",
                ),
            ],
            all_updates_rule=gcp.billing.BudgetAllUpdatesRuleArgs(
                monitoring_notification_channels=[ch_id for ch_id in notification_channel_ids] if notification_channel_ids else None,
                disable_default_iam_recipients=False,
            ) if notification_channel_ids else None,
        )

        # =================================================================
        # LAYER 7: VPC Service Controls (Optional)
        # =================================================================
        if enable_vpc_service_controls:
            print("[LANDING ZONE] Creating VPC Service Controls access perimeter...")

            access_policy = factory.create(
                "gcp:accesscontextmanager:AccessPolicy",
                f"access-policy-{project_name}",
                parent=f"organizations/{org_id}",
                title=f"archie-access-policy-{project_name}",
            )

            # Service perimeter around production projects
            prod_project_numbers = []
            if create_projects and 'production' in self.projects:
                prod_project_numbers.append(
                    self.projects['production'].number.apply(lambda n: f"projects/{n}")
                )

            if prod_project_numbers:
                self.service_perimeter = factory.create(
                    "gcp:accesscontextmanager:ServicePerimeter",
                    f"perimeter-prod-{project_name}",
                    parent=access_policy.name.apply(lambda n: f"accessPolicies/{n}"),
                    name=access_policy.name.apply(lambda n: f"accessPolicies/{n}/servicePerimeters/archie_prod_perimeter"),
                    title=f"archie-prod-perimeter-{project_name}",
                    perimeter_type="PERIMETER_TYPE_REGULAR",
                    status=gcp.accesscontextmanager.ServicePerimeterStatusArgs(
                        resources=prod_project_numbers,
                        restricted_services=[
                            "bigquery.googleapis.com",
                            "storage.googleapis.com",
                            "sqladmin.googleapis.com",
                        ],
                    ),
                    opts=pulumi.ResourceOptions(depends_on=[access_policy]),
                )

        # =================================================================
        # LAYER 8: IAM -- Org-Level Role Bindings
        # =================================================================
        print("[LANDING ZONE] Configuring org-level IAM roles...")

        org_admin_email = self._cfg('org_admin_email', '')
        billing_admin_email = self._cfg('billing_admin_email', '')
        security_admin_email = self._cfg('security_admin_email', '')
        network_admin_email = self._cfg('network_admin_email', '')

        iam_bindings = [
            ("org-admin", "roles/resourcemanager.organizationAdmin", org_admin_email),
            ("billing-admin", "roles/billing.admin", billing_admin_email),
            ("security-admin", "roles/iam.securityAdmin", security_admin_email),
            ("network-admin", "roles/compute.networkAdmin", network_admin_email),
        ]

        for binding_key, role, email in iam_bindings:
            if email:
                factory.create(
                    "gcp:organizations:IAMMember",
                    f"iam-{binding_key}-{project_name}",
                    org_id=org_id,
                    role=role,
                    member=f"user:{email}",
                )

        # =================================================================
        # OUTPUTS
        # =================================================================
        print("[LANDING ZONE] GCP Landing Zone deployment complete!")

        outputs: Dict[str, Any] = {
            "org_id": org_id,
            "environment": environment,
        }

        # Folder outputs
        for folder_key, folder in self.folders.items():
            outputs[f"folder_{folder_key.replace('-', '_')}_id"] = folder.name
            outputs[f"folder_{folder_key.replace('-', '_')}_display_name"] = folder.display_name

        # Project outputs
        for proj_key, proj in self.projects.items():
            outputs[f"project_{proj_key.replace('-', '_')}_id"] = proj.project_id
            outputs[f"project_{proj_key.replace('-', '_')}_number"] = proj.number

        # Org policy outputs
        for policy_key, policy in self.org_policies.items():
            outputs[f"orgpolicy_{policy_key.replace('-', '_')}_name"] = policy.name

        # Logging outputs
        if self.log_sink:
            outputs["log_sink_name"] = self.log_sink.name
            outputs["log_sink_destination"] = log_sink_destination
        if self.log_dataset:
            outputs["log_dataset_id"] = self.log_dataset.dataset_id
        if self.log_bucket_storage:
            outputs["log_bucket_name"] = self.log_bucket_storage.name

        # Budget outputs
        if self.budget:
            outputs["budget_name"] = self.budget.display_name
            outputs["budget_amount"] = str(budget_amount)

        # VPC Service Controls outputs
        if self.service_perimeter:
            outputs["service_perimeter_name"] = self.service_perimeter.name

        # Export all outputs (Rule #2, #7)
        for key, value in outputs.items():
            pulumi.export(key, value)

        return outputs

    def get_outputs(self) -> Dict[str, Any]:
        """Get template outputs"""
        outputs: Dict[str, Any] = {}

        for folder_key, folder in self.folders.items():
            outputs[f"folder_{folder_key.replace('-', '_')}_id"] = folder.name if folder else None

        for proj_key, proj in self.projects.items():
            outputs[f"project_{proj_key.replace('-', '_')}_id"] = proj.project_id if proj else None

        for policy_key, policy in self.org_policies.items():
            outputs[f"orgpolicy_{policy_key.replace('-', '_')}_name"] = policy.name if policy else None

        if self.log_sink:
            outputs["log_sink_name"] = self.log_sink.name
        if self.log_dataset:
            outputs["log_dataset_id"] = self.log_dataset.dataset_id
        if self.log_bucket_storage:
            outputs["log_bucket_name"] = self.log_bucket_storage.name
        if self.budget:
            outputs["budget_name"] = self.budget.display_name
        if self.service_perimeter:
            outputs["service_perimeter_name"] = self.service_perimeter.name

        return outputs

    @classmethod
    def get_metadata(cls) -> Dict[str, Any]:
        """Template metadata for marketplace registration"""
        return {
            "name": "gcp-landing-zone",
            "title": "Organization Landing Zone",
            "description": "Enterprise-grade GCP organization governance with folder hierarchy, org policies, centralized audit logging, budgets, VPC Service Controls, and org-level IAM.",
            "category": "governance",
            "version": "1.0.0",
            "author": "Archie",
            "cloud": "gcp",
            "environment": "foundation",
            "base_cost": "$5/month",
            "tags": ["organization", "landing-zone", "governance", "security", "compliance", "gcp"],
            "features": [
                "Folder hierarchy with customizable structure (Shared, Production, Non-Prod, Sandbox)",
                "Project Factory with standard labels and essential APIs enabled",
                "Organization Policies enforcing VM IP, Cloud SQL, Bucket Access, Shared VPC restrictions",
                "Resource location restriction to approved regions",
                "Centralized audit logging via organization sink to BigQuery or Cloud Storage",
                "Budget alerts at 50%, 80%, and 100% thresholds on billing account",
                "Cloud Monitoring notification channels and alert policies",
                "VPC Service Controls access perimeter for sensitive projects (optional)",
                "Org-level IAM role bindings for Admin, Billing, Security, and Network roles",
            ],
            "deployment_time": "5-10 minutes",
            "complexity": "advanced",
            "use_cases": [
                "Enterprise GCP organization setup",
                "Multi-project governance and compliance",
                "Cloud landing zone for regulated industries",
                "Centralized audit and cost management",
            ],
            "pillars": [
                {
                    "title": "Security",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Defense-in-depth with org policies, VPC Service Controls, and IAM governance",
                    "practices": [
                        "Organization policies enforce no public VMs, no public Cloud SQL, uniform bucket access",
                        "VPC Service Controls create security perimeters around sensitive projects",
                        "Org-level IAM with least-privilege role assignments",
                        "Centralized audit logging captures all API activity across the organization",
                        "Resource location restrictions prevent unauthorized region usage",
                    ]
                },
                {
                    "title": "Operational Excellence",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Centralized governance with automated multi-project management",
                    "practices": [
                        "Folder hierarchy provides logical project organization aligned to environments",
                        "Project Factory automates project creation with consistent labels and API enablement",
                        "Organization sink aggregates audit logs from all projects in one location",
                        "Infrastructure as Code ensures repeatable landing zone deployments",
                        "Monitoring notification channels enable proactive alerting",
                    ]
                },
                {
                    "title": "Cost Optimization",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Built-in budget alerting with multi-threshold notifications",
                    "practices": [
                        "Billing budget with 50%, 80%, and 100% spend threshold alerts",
                        "Email notification channels for immediate budget breach awareness",
                        "Organization policies prevent unauthorized resource sprawl via region restrictions",
                        "Cloud Logging lifecycle policies reduce long-term storage costs",
                        "Governance services (folders, org policies, IAM) incur no additional charges",
                    ]
                },
                {
                    "title": "Reliability",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Resilient governance layer with Google-managed service availability",
                    "practices": [
                        "Organization policies are enforced at the API layer with zero downtime risk",
                        "BigQuery audit log dataset provides durable, queryable log storage",
                        "Cloud Storage lifecycle transitions ensure long-term log retention",
                        "Google-managed services (folders, IAM, org policies) have built-in HA",
                        "VPC Service Controls add network-level protection without single points of failure",
                    ]
                },
                {
                    "title": "Performance Efficiency",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Lightweight governance layer with no impact on workload performance",
                    "practices": [
                        "Organization policies and folders add zero latency to workloads",
                        "BigQuery provides serverless, high-performance audit log querying",
                        "VPC Service Controls enforce at network edge with no application overhead",
                        "Project Factory uses auto_create_network=False to avoid default VPC overhead",
                        "Region restrictions simplify capacity planning and reduce blast radius",
                    ]
                },
                {
                    "title": "Sustainability",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Serverless governance services minimize resource consumption",
                    "practices": [
                        "All governance services are fully managed with no idle compute",
                        "Region restrictions reduce unnecessary infrastructure sprawl",
                        "Centralized logging eliminates duplicate log storage across projects",
                        "Cloud Storage lifecycle transitions to Coldline minimize active storage energy",
                        "Shared Google infrastructure for organization and IAM services",
                    ]
                },
            ]
        }

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        """Get configuration schema for the UI"""
        return {
            "type": "object",
            "properties": {
                "project_name": {
                    "type": "string",
                    "default": "my-org",
                    "title": "Organization Name",
                    "description": "Name for the landing zone (used in resource naming)",
                    "order": 1,
                    "group": "Essentials",
                    "isEssential": True,
                },
                "environment": {
                    "type": "string",
                    "default": "foundation",
                    "title": "Environment",
                    "description": "Deployment environment label",
                    "enum": ["foundation", "dev", "staging", "prod"],
                    "order": 2,
                    "group": "Essentials",
                    "isEssential": True,
                },
                "org_id": {
                    "type": "string",
                    "default": "",
                    "title": "Organization ID",
                    "description": "GCP Organization ID (numeric)",
                    "order": 3,
                    "group": "Essentials",
                    "isEssential": True,
                },
                "billing_account_id": {
                    "type": "string",
                    "default": "",
                    "title": "Billing Account ID",
                    "description": "GCP Billing Account ID (format: XXXXXX-XXXXXX-XXXXXX)",
                    "order": 4,
                    "group": "Essentials",
                    "isEssential": True,
                },
                "folder_names": {
                    "type": "string",
                    "default": "shared,production,nonprod,sandbox",
                    "title": "Folder Names",
                    "description": "Comma-separated list of folders to create under the organization",
                    "order": 10,
                    "group": "Organization Structure",
                },
                "create_projects": {
                    "type": "boolean",
                    "default": False,
                    "title": "Create Projects",
                    "description": "Create a GCP project inside each folder with standard labels and APIs enabled",
                    "order": 11,
                    "group": "Organization Structure",
                    "cost_impact": "+$0 (projects are free, resources inside cost)",
                },
                "project_prefix": {
                    "type": "string",
                    "default": "my-org",
                    "title": "Project Prefix",
                    "description": "Prefix for auto-created project IDs (e.g. prefix-production, prefix-sandbox)",
                    "order": 12,
                    "group": "Organization Structure",
                    "conditional": {"field": "create_projects"},
                },
                "allowed_regions": {
                    "type": "string",
                    "default": "us-central1,us-east1,europe-west1",
                    "title": "Allowed Regions",
                    "description": "Comma-separated list of GCP regions workloads can deploy to",
                    "order": 20,
                    "group": "Governance",
                },
                "enable_vpc_service_controls": {
                    "type": "boolean",
                    "default": False,
                    "title": "Enable VPC Service Controls",
                    "description": "Create an access perimeter around production projects to prevent data exfiltration",
                    "order": 21,
                    "group": "Governance",
                    "cost_impact": "+$0 (no charge for VPC SC)",
                },
                "log_sink_destination": {
                    "type": "string",
                    "default": "bigquery",
                    "title": "Log Sink Destination",
                    "description": "Where to send organization audit logs",
                    "enum": ["bigquery", "storage"],
                    "order": 30,
                    "group": "Logging & Monitoring",
                },
                "budget_amount": {
                    "type": "number",
                    "default": 10000,
                    "title": "Monthly Budget (USD)",
                    "description": "Monthly spending limit for budget alerts (alerts at 50%, 80%, 100%)",
                    "order": 31,
                    "group": "Logging & Monitoring",
                },
                "budget_contact_emails": {
                    "type": "string",
                    "default": "",
                    "title": "Budget Alert Emails",
                    "description": "Comma-separated email addresses for budget alert notifications",
                    "order": 32,
                    "group": "Logging & Monitoring",
                },
                "org_admin_email": {
                    "type": "string",
                    "default": "",
                    "title": "Org Admin Email",
                    "description": "Email for Organization Admin role binding (leave blank to skip)",
                    "order": 40,
                    "group": "IAM Roles",
                },
                "billing_admin_email": {
                    "type": "string",
                    "default": "",
                    "title": "Billing Admin Email",
                    "description": "Email for Billing Admin role binding (leave blank to skip)",
                    "order": 41,
                    "group": "IAM Roles",
                },
                "security_admin_email": {
                    "type": "string",
                    "default": "",
                    "title": "Security Admin Email",
                    "description": "Email for Security Admin role binding (leave blank to skip)",
                    "order": 42,
                    "group": "IAM Roles",
                },
                "network_admin_email": {
                    "type": "string",
                    "default": "",
                    "title": "Network Admin Email",
                    "description": "Email for Network Admin role binding (leave blank to skip)",
                    "order": 43,
                    "group": "IAM Roles",
                },
                "team_name": {
                    "type": "string",
                    "default": "",
                    "title": "Team Name",
                    "description": "Team that owns this landing zone",
                    "order": 50,
                    "group": "Tags",
                },
            },
            "required": ["project_name", "org_id", "billing_account_id"],
        }
