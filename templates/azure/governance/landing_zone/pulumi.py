"""
Azure Landing Zone with Management Groups and Multi-Subscription Governance

Enterprise-grade Azure governance architecture based on Microsoft Cloud Adoption Framework.

Core components:
- Management Group hierarchy: Root -> Platform (Identity, Management, Connectivity) -> Landing Zones (Corp, Online) -> Sandbox
- Subscription assignment to management groups (via config, not creating subscriptions)
- Azure Policy assignments: Allowed Locations, Require Tags, Deny Public IP (optional), Audit VMs without Managed Disks
- Azure Defender for Cloud (Standard tier on Key Vault, Storage, SQL, ARM)
- Diagnostic Settings -> Log Analytics Workspace (centralized logging)
- Activity Log export to Log Analytics
- Budget on Management Group with notification thresholds (50%, 80%, 100%)
- Network Watcher (per-region)
- Azure Monitor Action Group for alerts

Management Group hierarchy:
  Root MG
  ├── Platform
  │   ├── Identity        (AAD, domain services)
  │   ├── Management      (logging, monitoring, automation)
  │   └── Connectivity    (hub networking, DNS, ExpressRoute)
  ├── Landing Zones
  │   ├── Corp            (internal-facing workloads)
  │   └── Online          (internet-facing workloads)
  └── Sandbox             (experimentation, no policy enforcement)
"""

from typing import Any, Dict, List, Optional
from pathlib import Path
import json
import pulumi
import pulumi_azure_native as azure_native

from provisioner.templates.base import InfrastructureTemplate, template_registry
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory


@template_registry("azure-landing-zone")
class AzureLandingZoneTemplate(InfrastructureTemplate):
    """
    Azure Landing Zone -- Management Groups, Policy Assignments,
    Defender for Cloud, Log Analytics, Budgets, Network Watcher.
    """

    def __init__(self, name: str = None, config: Dict[str, Any] = None, azure_config: Dict[str, Any] = None, **kwargs):
        raw_config = config or azure_config or kwargs or {}

        if name is None:
            name = (
                raw_config.get('project_name') or
                raw_config.get('projectName') or
                raw_config.get('parameters', {}).get('azure', {}).get('project_name') or
                'landing-zone'
            )

        super().__init__(name, raw_config)
        self.config = raw_config

        # Resource references (populated in create())
        self.root_mg: Optional[object] = None
        self.management_groups: Dict[str, object] = {}
        self.log_analytics_workspace: Optional[object] = None
        self.action_group: Optional[object] = None
        self.resource_group: Optional[object] = None
        self.network_watcher: Optional[object] = None

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

    def _get_bool(self, key: str, default: bool = False) -> bool:
        """Read boolean config handling string/bool/Decimal from DynamoDB"""
        val = self._cfg(key, default)
        if isinstance(val, bool):
            return val
        if isinstance(val, str):
            return val.lower() in ('true', '1', 'yes')
        return bool(val)

    def _get_int(self, key: str, default: int = 0) -> int:
        """Read integer config handling string/int from DynamoDB"""
        val = self._cfg(key, default)
        try:
            return int(val)
        except (ValueError, TypeError):
            return default

    def create_infrastructure(self) -> Dict[str, Any]:
        return self.create()

    def create(self) -> Dict[str, Any]:
        project = self._cfg('project_name', 'myorg')
        env = self._cfg('environment', 'foundation')
        location = self._cfg('location', 'eastus')
        team_name = self._cfg('team_name', '')
        root_mg_name = self._cfg('root_management_group_name', f'{project}-root')

        # Parse multi-value config
        allowed_locations = [loc.strip() for loc in self._cfg('allowed_locations', 'eastus,westus2,northeurope').split(',')]
        require_tag_names = [t.strip() for t in self._cfg('require_tag_names', 'Environment,ManagedBy,Project').split(',')]
        budget_contact_emails = [e.strip() for e in self._cfg('budget_contact_emails', 'platform@company.com').split(',')]
        budget_amount = self._get_int('budget_amount', 10000)
        enable_defender = self._get_bool('enable_defender', True)
        enable_deny_public_ip = self._get_bool('enable_policy_deny_public_ip', False)
        log_retention_days = self._get_int('log_retention_days', 90)

        # Standard tags
        tags = {
            'Project': project,
            'Environment': env,
            'ManagedBy': 'Archie',
            'Template': 'azure-landing-zone',
        }
        if team_name:
            tags['Team'] = team_name
        tags.update(self._cfg('tags', {}) or {})

        # =================================================================
        # LAYER 1: Management Group Hierarchy
        # =================================================================
        print("[LANDING ZONE] Creating Management Group hierarchy...")

        # Root Management Group
        self.root_mg = factory.create(
            "azure-native:management:ManagementGroup",
            f"mg-root-{project}",
            group_id=root_mg_name,
            display_name=f"{project} Root",
            details=azure_native.management.CreateManagementGroupDetailsArgs(
                parent=azure_native.management.CreateParentGroupInfoArgs(
                    id=f"/providers/Microsoft.Management/managementGroups/{self._cfg('tenant_id', '')}",
                ) if self._cfg('tenant_id') else None,
            ) if self._cfg('tenant_id') else None,
        )

        root_mg_id = self.root_mg.id

        # Platform Management Group
        self.management_groups['platform'] = factory.create(
            "azure-native:management:ManagementGroup",
            f"mg-platform-{project}",
            group_id=f"{root_mg_name}-platform",
            display_name="Platform",
            details=azure_native.management.CreateManagementGroupDetailsArgs(
                parent=azure_native.management.CreateParentGroupInfoArgs(
                    id=root_mg_id,
                ),
            ),
            opts=pulumi.ResourceOptions(depends_on=[self.root_mg]),
        )

        platform_mg_id = self.management_groups['platform'].id

        # Platform child MGs: Identity, Management, Connectivity
        for child_key, child_display in [("identity", "Identity"), ("management", "Management"), ("connectivity", "Connectivity")]:
            self.management_groups[child_key] = factory.create(
                "azure-native:management:ManagementGroup",
                f"mg-{child_key}-{project}",
                group_id=f"{root_mg_name}-{child_key}",
                display_name=child_display,
                details=azure_native.management.CreateManagementGroupDetailsArgs(
                    parent=azure_native.management.CreateParentGroupInfoArgs(
                        id=platform_mg_id,
                    ),
                ),
                opts=pulumi.ResourceOptions(depends_on=[self.management_groups['platform']]),
            )

        # Landing Zones Management Group
        self.management_groups['landing-zones'] = factory.create(
            "azure-native:management:ManagementGroup",
            f"mg-landing-zones-{project}",
            group_id=f"{root_mg_name}-landing-zones",
            display_name="Landing Zones",
            details=azure_native.management.CreateManagementGroupDetailsArgs(
                parent=azure_native.management.CreateParentGroupInfoArgs(
                    id=root_mg_id,
                ),
            ),
            opts=pulumi.ResourceOptions(depends_on=[self.root_mg]),
        )

        lz_mg_id = self.management_groups['landing-zones'].id

        # Landing Zone child MGs: Corp, Online
        for child_key, child_display in [("corp", "Corp"), ("online", "Online")]:
            self.management_groups[child_key] = factory.create(
                "azure-native:management:ManagementGroup",
                f"mg-{child_key}-{project}",
                group_id=f"{root_mg_name}-{child_key}",
                display_name=child_display,
                details=azure_native.management.CreateManagementGroupDetailsArgs(
                    parent=azure_native.management.CreateParentGroupInfoArgs(
                        id=lz_mg_id,
                    ),
                ),
                opts=pulumi.ResourceOptions(depends_on=[self.management_groups['landing-zones']]),
            )

        # Sandbox Management Group (child of root)
        self.management_groups['sandbox'] = factory.create(
            "azure-native:management:ManagementGroup",
            f"mg-sandbox-{project}",
            group_id=f"{root_mg_name}-sandbox",
            display_name="Sandbox",
            details=azure_native.management.CreateManagementGroupDetailsArgs(
                parent=azure_native.management.CreateParentGroupInfoArgs(
                    id=root_mg_id,
                ),
            ),
            opts=pulumi.ResourceOptions(depends_on=[self.root_mg]),
        )

        # =================================================================
        # LAYER 2: Subscription Assignments (Optional)
        # =================================================================
        subscription_assignments = self._cfg('subscription_assignments', {})
        if isinstance(subscription_assignments, dict):
            for mg_key, sub_ids in subscription_assignments.items():
                if mg_key in self.management_groups and sub_ids:
                    sub_list = sub_ids if isinstance(sub_ids, list) else [sub_ids]
                    for idx, sub_id in enumerate(sub_list):
                        factory.create(
                            "azure-native:management:ManagementGroupSubscription",
                            f"mg-sub-{mg_key}-{idx}-{project}",
                            group_id=self.management_groups[mg_key].name,
                            subscription_id=sub_id,
                            opts=pulumi.ResourceOptions(depends_on=[self.management_groups[mg_key]]),
                        )
                        print(f"[LANDING ZONE] Assigned subscription {sub_id} to {mg_key}")

        # =================================================================
        # LAYER 3: Resource Group for Landing Zone resources
        # =================================================================
        print("[LANDING ZONE] Creating resource group for governance resources...")

        rg_name = f"rg-governance-{project}-{env}"
        self.resource_group = factory.create(
            "azure-native:resources:ResourceGroup",
            f"rg-governance-{project}",
            resource_group_name=rg_name,
            location=location,
            tags={**tags, "Purpose": "Landing Zone Governance"},
        )

        # =================================================================
        # LAYER 4: Log Analytics Workspace (Centralized Logging)
        # =================================================================
        print("[LANDING ZONE] Creating Log Analytics workspace...")

        workspace_name = f"law-{project}-{env}"
        self.log_analytics_workspace = factory.create(
            "azure-native:operationalinsights:Workspace",
            f"law-{project}",
            workspace_name=workspace_name,
            resource_group_name=self.resource_group.name,
            location=location,
            sku=azure_native.operationalinsights.WorkspaceSkuArgs(
                name="PerGB2018",
            ),
            retention_in_days=log_retention_days,
            tags={**tags, "Purpose": "Centralized Logging"},
            opts=pulumi.ResourceOptions(depends_on=[self.resource_group]),
        )

        workspace_id = self.log_analytics_workspace.id

        # =================================================================
        # LAYER 5: Activity Log Diagnostic Setting (Subscription-level)
        # =================================================================
        print("[LANDING ZONE] Configuring Activity Log export to Log Analytics...")

        factory.create(
            "azure-native:insights:DiagnosticSetting",
            f"diag-activity-log-{project}",
            name=f"activity-log-{project}",
            resource_uri=f"/subscriptions/{self._cfg('subscription_id', '')}",
            workspace_id=workspace_id,
            logs=[
                azure_native.insights.LogSettingsArgs(
                    category="Administrative",
                    enabled=True,
                    retention_policy=azure_native.insights.RetentionPolicyArgs(
                        enabled=True,
                        days=log_retention_days,
                    ),
                ),
                azure_native.insights.LogSettingsArgs(
                    category="Security",
                    enabled=True,
                    retention_policy=azure_native.insights.RetentionPolicyArgs(
                        enabled=True,
                        days=log_retention_days,
                    ),
                ),
                azure_native.insights.LogSettingsArgs(
                    category="ServiceHealth",
                    enabled=True,
                    retention_policy=azure_native.insights.RetentionPolicyArgs(
                        enabled=True,
                        days=log_retention_days,
                    ),
                ),
                azure_native.insights.LogSettingsArgs(
                    category="Alert",
                    enabled=True,
                    retention_policy=azure_native.insights.RetentionPolicyArgs(
                        enabled=True,
                        days=log_retention_days,
                    ),
                ),
                azure_native.insights.LogSettingsArgs(
                    category="Recommendation",
                    enabled=True,
                    retention_policy=azure_native.insights.RetentionPolicyArgs(
                        enabled=True,
                        days=log_retention_days,
                    ),
                ),
                azure_native.insights.LogSettingsArgs(
                    category="Policy",
                    enabled=True,
                    retention_policy=azure_native.insights.RetentionPolicyArgs(
                        enabled=True,
                        days=log_retention_days,
                    ),
                ),
            ],
            opts=pulumi.ResourceOptions(depends_on=[self.log_analytics_workspace]),
        )

        # =================================================================
        # LAYER 6: Azure Policy Assignments
        # =================================================================
        print("[LANDING ZONE] Creating Azure Policy assignments...")

        # Policy 1: Allowed Locations
        # Built-in policy definition ID: e56962a6-4747-49cd-b67b-bf8b01975c4c
        factory.create(
            "azure-native:authorization:PolicyAssignment",
            f"policy-allowed-locations-{project}",
            policy_assignment_name=f"allowed-locations-{project}",
            scope=root_mg_id,
            policy_definition_id="/providers/Microsoft.Authorization/policyDefinitions/e56962a6-4747-49cd-b67b-bf8b01975c4c",
            display_name="Allowed Locations",
            description=f"Restrict resource deployment to approved regions: {', '.join(allowed_locations)}",
            parameters={
                "listOfAllowedLocations": azure_native.authorization.ParameterValuesValueArgs(
                    value=allowed_locations,
                ),
            },
            enforcement_mode="Default",
            opts=pulumi.ResourceOptions(depends_on=[self.root_mg]),
        )

        # Policy 2: Require Tags (one assignment per required tag)
        # Built-in policy definition ID: 871b6d14-10aa-478d-b466-ce391587f6cd (Require a tag on resources)
        for idx, tag_name in enumerate(require_tag_names):
            factory.create(
                "azure-native:authorization:PolicyAssignment",
                f"policy-require-tag-{tag_name.lower()}-{project}",
                policy_assignment_name=f"require-tag-{tag_name.lower()}-{project}",
                scope=self.management_groups['landing-zones'].id,
                policy_definition_id="/providers/Microsoft.Authorization/policyDefinitions/871b6d14-10aa-478d-b466-ce391587f6cd",
                display_name=f"Require Tag: {tag_name}",
                description=f"Deny resource creation without the '{tag_name}' tag in Landing Zones",
                parameters={
                    "tagName": azure_native.authorization.ParameterValuesValueArgs(
                        value=tag_name,
                    ),
                },
                enforcement_mode="Default",
                opts=pulumi.ResourceOptions(depends_on=[self.management_groups['landing-zones']]),
            )

        # Policy 3: Deny Public IP (optional)
        # Built-in policy definition ID: 6c112d4e-5bc7-47ae-a041-ea2d9dccd749
        if enable_deny_public_ip:
            factory.create(
                "azure-native:authorization:PolicyAssignment",
                f"policy-deny-public-ip-{project}",
                policy_assignment_name=f"deny-public-ip-{project}",
                scope=self.management_groups['corp'].id,
                policy_definition_id="/providers/Microsoft.Authorization/policyDefinitions/6c112d4e-5bc7-47ae-a041-ea2d9dccd749",
                display_name="Deny Public IP Addresses",
                description="Prevent creation of public IP addresses in Corp landing zone",
                enforcement_mode="Default",
                opts=pulumi.ResourceOptions(depends_on=[self.management_groups['corp']]),
            )

        # Policy 4: Audit VMs without Managed Disks
        # Built-in policy definition ID: 06a78e20-9358-41c9-923c-fb736d382a4d
        factory.create(
            "azure-native:authorization:PolicyAssignment",
            f"policy-audit-managed-disks-{project}",
            policy_assignment_name=f"audit-managed-disks-{project}",
            scope=root_mg_id,
            policy_definition_id="/providers/Microsoft.Authorization/policyDefinitions/06a78e20-9358-41c9-923c-fb736d382a4d",
            display_name="Audit VMs without Managed Disks",
            description="Audit virtual machines that do not use managed disks",
            enforcement_mode="Default",
            opts=pulumi.ResourceOptions(depends_on=[self.root_mg]),
        )

        # =================================================================
        # LAYER 7: Azure Defender for Cloud (Optional)
        # =================================================================
        defender_pricings = {}
        if enable_defender:
            print("[LANDING ZONE] Enabling Azure Defender for Cloud...")

            defender_resource_types = [
                ("KeyVaults", "Key Vault"),
                ("StorageAccounts", "Storage"),
                ("SqlServers", "SQL Servers"),
                ("Arm", "Resource Manager"),
            ]

            for resource_type, display in defender_resource_types:
                defender_pricings[resource_type] = factory.create(
                    "azure-native:security:Pricing",
                    f"defender-{resource_type.lower()}-{project}",
                    pricing_name=resource_type,
                    pricing_tier="Standard",
                )
                print(f"[LANDING ZONE]   Defender enabled for {display}")

        # =================================================================
        # LAYER 8: Budget on Root Management Group
        # =================================================================
        print(f"[LANDING ZONE] Creating budget (${budget_amount}/month)...")

        budget_notifications = {}

        # 50% threshold
        budget_notifications['actual_50_percent'] = azure_native.consumption.NotificationArgs(
            enabled=True,
            operator="GreaterThan",
            threshold=50,
            contact_emails=budget_contact_emails,
            threshold_type="Actual",
        )

        # 80% threshold
        budget_notifications['actual_80_percent'] = azure_native.consumption.NotificationArgs(
            enabled=True,
            operator="GreaterThan",
            threshold=80,
            contact_emails=budget_contact_emails,
            threshold_type="Actual",
        )

        # 100% threshold
        budget_notifications['actual_100_percent'] = azure_native.consumption.NotificationArgs(
            enabled=True,
            operator="GreaterThan",
            threshold=100,
            contact_emails=budget_contact_emails,
            threshold_type="Actual",
        )

        # Budget time period: current month to 1 year out
        import datetime
        now = datetime.datetime.utcnow()
        start_date = now.strftime("%Y-%m-01T00:00:00Z")
        end_date = (now.replace(year=now.year + 1)).strftime("%Y-%m-01T00:00:00Z")

        factory.create(
            "azure-native:consumption:Budget",
            f"budget-{project}",
            budget_name=f"budget-{project}-monthly",
            scope=root_mg_id,
            amount=budget_amount,
            category="Cost",
            time_grain="Monthly",
            time_period=azure_native.consumption.BudgetTimePeriodArgs(
                start_date=start_date,
                end_date=end_date,
            ),
            notifications=budget_notifications,
            opts=pulumi.ResourceOptions(depends_on=[self.root_mg]),
        )

        # =================================================================
        # LAYER 9: Network Watcher (per region)
        # =================================================================
        print("[LANDING ZONE] Creating Network Watcher...")

        self.network_watcher = factory.create(
            "azure-native:network:NetworkWatcher",
            f"nw-{project}-{location}",
            network_watcher_name=f"nw-{project}-{location}",
            resource_group_name=self.resource_group.name,
            location=location,
            tags=tags,
            opts=pulumi.ResourceOptions(depends_on=[self.resource_group]),
        )

        # =================================================================
        # LAYER 10: Azure Monitor Action Group (Alerts)
        # =================================================================
        print("[LANDING ZONE] Creating Azure Monitor Action Group...")

        email_receivers = []
        for idx, email in enumerate(budget_contact_emails):
            email_receivers.append(
                azure_native.insights.EmailReceiverArgs(
                    name=f"platform-team-{idx}",
                    email_address=email,
                    use_common_alert_schema=True,
                )
            )

        self.action_group = factory.create(
            "azure-native:insights:ActionGroup",
            f"ag-{project}",
            action_group_name=f"ag-{project}-platform",
            resource_group_name=self.resource_group.name,
            location="Global",
            group_short_name=f"{project[:10]}ag",
            enabled=True,
            email_receivers=email_receivers,
            tags=tags,
            opts=pulumi.ResourceOptions(depends_on=[self.resource_group]),
        )

        # =================================================================
        # OUTPUTS
        # =================================================================
        print("[LANDING ZONE] Azure Landing Zone deployment complete!")

        outputs = {
            "root_management_group_id": self.root_mg.id,
            "root_management_group_name": root_mg_name,
            "platform_mg_id": self.management_groups['platform'].id,
            "identity_mg_id": self.management_groups['identity'].id,
            "management_mg_id": self.management_groups['management'].id,
            "connectivity_mg_id": self.management_groups['connectivity'].id,
            "landing_zones_mg_id": self.management_groups['landing-zones'].id,
            "corp_mg_id": self.management_groups['corp'].id,
            "online_mg_id": self.management_groups['online'].id,
            "sandbox_mg_id": self.management_groups['sandbox'].id,
            "log_analytics_workspace_id": self.log_analytics_workspace.id,
            "log_analytics_workspace_name": workspace_name,
            "resource_group_name": rg_name,
            "action_group_id": self.action_group.id,
            "network_watcher_id": self.network_watcher.id,
            "environment": env,
        }

        if defender_pricings:
            outputs["defender_enabled_services"] = list(defender_pricings.keys())

        # Export all outputs (Rule #2, #7)
        for key, value in outputs.items():
            pulumi.export(key, value)

        return outputs

    def get_outputs(self) -> Dict[str, Any]:
        """Get template outputs"""
        if not self.root_mg:
            return {}

        outputs = {
            "root_management_group_id": self.root_mg.id if self.root_mg else None,
            "log_analytics_workspace_id": self.log_analytics_workspace.id if self.log_analytics_workspace else None,
            "resource_group_name": self.resource_group.name if self.resource_group else None,
            "action_group_id": self.action_group.id if self.action_group else None,
            "network_watcher_id": self.network_watcher.id if self.network_watcher else None,
        }

        for mg_key, mg in self.management_groups.items():
            outputs[f"{mg_key.replace('-', '_')}_mg_id"] = mg.id

        return outputs

    @classmethod
    def get_metadata(cls) -> Dict[str, Any]:
        """Template metadata for marketplace registration"""
        return {
            "name": "azure-landing-zone",
            "title": "Azure Landing Zone with Management Groups",
            "description": "Enterprise-grade Azure governance architecture based on Microsoft Cloud Adoption Framework. Deploys Management Group hierarchy, Azure Policy, Defender for Cloud, centralized logging, budgets, and monitoring.",
            "category": "governance",
            "version": "1.0.0",
            "author": "Archie",
            "cloud": "azure",
            "environment": "foundation",
            "base_cost": "$15/month",
            "tags": ["landing-zone", "governance", "management-groups", "policy", "defender", "compliance", "caf"],
            "features": [
                "Management Group hierarchy following Cloud Adoption Framework",
                "Azure Policy assignments for location, tagging, and compliance",
                "Azure Defender for Cloud on Key Vault, Storage, SQL, and ARM",
                "Centralized Log Analytics workspace with Activity Log export",
                "Budget alerts at 50%, 80%, and 100% spend thresholds",
                "Network Watcher for network diagnostics per region",
                "Azure Monitor Action Group for platform alerting",
                "Subscription assignment to management groups via config",
                "Optional Deny Public IP policy for Corp landing zone",
            ],
            "deployment_time": "5-10 minutes",
            "complexity": "advanced",
            "use_cases": [
                "New Azure tenant governance setup",
                "Cloud Adoption Framework landing zone",
                "Multi-subscription enterprise governance",
                "Compliance baseline for regulated industries",
                "Centralized logging and monitoring foundation",
            ],
            "pillars": [
                {
                    "title": "Operational Excellence",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Centralized governance with Management Group hierarchy and policy enforcement",
                    "practices": [
                        "Management Groups provide hierarchical governance at scale",
                        "Azure Policy enforces organizational standards automatically",
                        "Centralized Log Analytics for unified operational visibility",
                        "Activity Log export captures all subscription-level operations",
                        "Infrastructure as Code for repeatable landing zone deployments",
                    ]
                },
                {
                    "title": "Security",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Defense-in-depth with Defender for Cloud, policies, and centralized logging",
                    "practices": [
                        "Azure Defender for Cloud on Key Vault, Storage, SQL, and ARM",
                        "Allowed Locations policy restricts resource deployment regions",
                        "Required Tags policy enforces governance metadata on all resources",
                        "Optional Deny Public IP policy for internal-only landing zones",
                        "Centralized security logging via Log Analytics workspace",
                    ]
                },
                {
                    "title": "Reliability",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Azure-managed governance services with built-in resilience",
                    "practices": [
                        "Management Groups and Policy are globally available Azure services",
                        "Log Analytics workspace provides durable centralized log storage",
                        "Network Watcher enables network diagnostics and troubleshooting",
                        "Action Group delivers multi-channel alert notifications",
                        "Budget alerts provide proactive cost anomaly detection",
                    ]
                },
                {
                    "title": "Cost Optimization",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Low-cost governance with budget controls and spend visibility",
                    "practices": [
                        "Management Groups and Azure Policy are free services",
                        "Budget alerts at 50%, 80%, and 100% thresholds prevent overspend",
                        "Log Analytics uses cost-effective PerGB2018 pricing tier",
                        "Configurable log retention avoids unnecessary storage costs",
                        "Allowed Locations policy prevents accidental resource sprawl",
                    ]
                },
                {
                    "title": "Performance Efficiency",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Lightweight governance layer with zero workload overhead",
                    "practices": [
                        "Policy evaluation adds no latency to workload operations",
                        "Management Groups organize subscriptions without runtime impact",
                        "Defender for Cloud uses agentless scanning where possible",
                        "Log Analytics ingestion scales automatically with volume",
                        "Network Watcher provides on-demand diagnostics without agents",
                    ]
                },
                {
                    "title": "Sustainability",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Fully managed services minimize operational resource consumption",
                    "practices": [
                        "All governance services are fully managed with no dedicated compute",
                        "Centralized logging eliminates duplicate log storage across subscriptions",
                        "Policy enforcement prevents unnecessary resource creation",
                        "Configurable retention periods reduce long-term storage footprint",
                        "Region restriction reduces infrastructure sprawl and energy usage",
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
                    "default": "myorg",
                    "title": "Project Name",
                    "description": "Organization name used in resource naming",
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
                "location": {
                    "type": "string",
                    "default": "eastus",
                    "title": "Primary Location",
                    "description": "Azure region for governance resources (Log Analytics, Resource Group)",
                    "enum": ["eastus", "eastus2", "westus2", "westus3", "centralus", "northeurope", "westeurope", "uksouth", "southeastasia", "australiaeast"],
                    "order": 3,
                    "group": "Essentials",
                    "isEssential": True,
                },
                "root_management_group_name": {
                    "type": "string",
                    "default": "myorg-root",
                    "title": "Root Management Group Name",
                    "description": "ID and display prefix for the root management group",
                    "order": 10,
                    "group": "Management Groups",
                },
                "allowed_locations": {
                    "type": "string",
                    "default": "eastus,westus2,northeurope",
                    "title": "Allowed Locations",
                    "description": "Comma-separated Azure regions where resources can be deployed",
                    "order": 20,
                    "group": "Policy Configuration",
                },
                "require_tag_names": {
                    "type": "string",
                    "default": "Environment,ManagedBy,Project",
                    "title": "Required Tag Names",
                    "description": "Comma-separated tag names that must be present on all resources in Landing Zones",
                    "order": 21,
                    "group": "Policy Configuration",
                },
                "enable_policy_deny_public_ip": {
                    "type": "boolean",
                    "default": False,
                    "title": "Deny Public IP (Corp LZ)",
                    "description": "Block public IP address creation in the Corp landing zone",
                    "order": 22,
                    "group": "Policy Configuration",
                },
                "enable_defender": {
                    "type": "boolean",
                    "default": True,
                    "title": "Enable Defender for Cloud",
                    "description": "Enable Azure Defender Standard tier on Key Vault, Storage, SQL, and ARM",
                    "order": 30,
                    "group": "Security",
                    "cost_impact": "+$15/month per service",
                },
                "budget_amount": {
                    "type": "number",
                    "default": 10000,
                    "title": "Monthly Budget (USD)",
                    "description": "Monthly spending limit with alerts at 50%, 80%, and 100%",
                    "minimum": 100,
                    "order": 40,
                    "group": "Cost Management",
                },
                "budget_contact_emails": {
                    "type": "string",
                    "default": "platform@company.com",
                    "title": "Budget Alert Emails",
                    "description": "Comma-separated email addresses for budget and alert notifications",
                    "order": 41,
                    "group": "Cost Management",
                },
                "log_retention_days": {
                    "type": "number",
                    "default": 90,
                    "title": "Log Retention (Days)",
                    "description": "Number of days to retain logs in Log Analytics workspace",
                    "minimum": 30,
                    "maximum": 730,
                    "order": 50,
                    "group": "Logging",
                },
                "team_name": {
                    "type": "string",
                    "default": "",
                    "title": "Team Name",
                    "description": "Team that owns this landing zone",
                    "order": 90,
                    "group": "Tags",
                },
            },
            "required": ["project_name", "location"],
        }
