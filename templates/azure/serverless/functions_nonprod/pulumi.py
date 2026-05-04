"""
Azure Functions Non-Prod Template

Serverless compute with consumption plan for dev/staging environments.
Function App + Storage Account + Application Insights + Managed Identity.

Base cost (~$0-5/mo — consumption pricing):
- Function App (Consumption/Dynamic plan, pay-per-execution)
- Storage Account (Standard_LRS, required by Functions runtime)
- Application Insights (per-GB ingestion pricing)
- User-Assigned Managed Identity
- HTTPS-only enforcement
- TLS 1.2 minimum on storage
"""

from typing import Any, Dict, Optional
from pathlib import Path
import pulumi
import pulumi_azure_native as azure_native

from provisioner.templates.base import InfrastructureTemplate, template_registry
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory
from provisioner.utils.azure.tags import get_standard_tags, get_app_service_tags
from provisioner.utils.azure.naming import get_resource_name, get_storage_account_name


@template_registry("azure-functions-nonprod")
class AzureFunctionsNonProdTemplate(InfrastructureTemplate):
    """
    Azure Functions Non-Prod Template

    Serverless compute with consumption plan for non-production environments.
    Includes storage account, App Insights, and managed identity.
    """

    def __init__(self, name: str = None, config: Dict[str, Any] = None, azure_config: Dict[str, Any] = None, **kwargs):
        """Initialize Azure Functions Non-Prod template"""
        raw_config = config or azure_config or kwargs or {}

        if name is None:
            name = (
                raw_config.get('project_name') or
                raw_config.get('projectName') or
                raw_config.get('parameters', {}).get('azure', {}).get('project_name') or
                'azure-functions-nonprod'
            )

        super().__init__(name, raw_config)
        self.config = raw_config

        # Resource references (populated in create())
        self.resource_group: Optional[object] = None
        self.storage_account: Optional[object] = None
        self.app_insights: Optional[object] = None
        self.identity: Optional[object] = None
        self.app_service_plan: Optional[object] = None
        self.function_app: Optional[object] = None

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
        """Deploy Functions infrastructure (implements abstract method)"""
        return self.create()

    def create(self) -> Dict[str, Any]:
        """Deploy complete Azure Functions infrastructure"""

        # Read config
        project = self._cfg('project_name', 'myapp')
        env = self._cfg('environment', 'dev')
        location = self._cfg('location', 'eastus')
        team_name = self._cfg('team_name', '')
        runtime = self._cfg('runtime', 'node')
        runtime_version = self._cfg('runtime_version', '18')
        functions_version = self._cfg('functions_version', '~4')

        enable_app_insights = self._cfg('enable_app_insights', True)
        if isinstance(enable_app_insights, str):
            enable_app_insights = enable_app_insights.lower() in ('true', '1', 'yes')

        # Standard tags
        tags = get_standard_tags(project=project, environment=env)
        tags['ManagedBy'] = 'Archie'
        tags['Template'] = 'azure-functions-nonprod'
        tags.update(self._cfg('tags', {}))
        if team_name:
            tags['Team'] = team_name

        # Resource names (prefer injected on upgrade — Rule #3)
        rg_name = self._cfg('resource_group_name') or f'rg-{project}-{env}-func'
        storage_name = self._cfg('storage_account_name') or f'st{project}{env}func'.replace('-', '')[:24]
        plan_name = self._cfg('app_service_plan_name') or f'plan-{project}-{env}'
        func_name = self._cfg('function_app_name') or f'func-{project}-{env}'
        insights_name = self._cfg('app_insights_name') or f'ai-{project}-{env}'
        identity_name = self._cfg('identity_name') or f'id-{project}-{env}-func'

        # =================================================================
        # LAYER 1: Resource Group
        # =================================================================

        # Brownfield: use existing resource group if provided
        existing_rg = self._cfg('existing_resource_group', '')

        if existing_rg:
            self.resource_group = azure_native.resources.ResourceGroup.get(
                'existing-rg',
                id=f'/subscriptions/{self._cfg("azure_subscription_id", "")}/resourceGroups/{existing_rg}',
            )
            rg_name = existing_rg
        else:
            self.resource_group = factory.create(
                'azure-native:resources:ResourceGroup', rg_name,
                resource_group_name=rg_name,
                location=location,
                tags={**tags, 'Purpose': 'functions'},
            )

        # =================================================================
        # LAYER 2: Storage Account (required by Functions runtime)
        # =================================================================

        self.storage_account = factory.create(
            'azure-native:storage:StorageAccount', storage_name,
            account_name=storage_name,
            resource_group_name=self.resource_group.name,
            location=location,
            sku={'name': 'Standard_LRS'},
            kind='StorageV2',
            minimum_tls_version='TLS1_2',
            allow_blob_public_access=False,
            tags=tags,
        )

        # =================================================================
        # LAYER 3: Application Insights (optional)
        # =================================================================

        if enable_app_insights:
            self.app_insights = factory.create(
                'azure-native:insights:Component', insights_name,
                resource_name_=insights_name,
                resource_group_name=self.resource_group.name,
                location=location,
                kind='web',
                application_type='web',
                tags=tags,
            )

        # =================================================================
        # LAYER 4: User-Assigned Managed Identity
        # =================================================================

        self.identity = factory.create(
            'azure-native:managedidentity:UserAssignedIdentity', identity_name,
            resource_name_=identity_name,
            resource_group_name=self.resource_group.name,
            location=location,
            tags=tags,
        )

        # =================================================================
        # LAYER 5: Consumption Plan
        # =================================================================

        self.app_service_plan = factory.create(
            'azure-native:web:AppServicePlan', plan_name,
            name=plan_name,
            resource_group_name=self.resource_group.name,
            location=location,
            kind='FunctionApp',
            reserved=True,
            sku={'name': 'Y1', 'tier': 'Dynamic'},
            tags=tags,
        )

        # =================================================================
        # LAYER 6: Function App
        # =================================================================

        runtime_map = {
            'node': 'node',
            'python': 'python',
            'dotnet': 'dotnet-isolated',
            'java': 'java',
            'powershell': 'powershell',
        }
        worker_runtime = runtime_map.get(runtime, 'node')

        app_settings = [
            {'name': 'FUNCTIONS_EXTENSION_VERSION', 'value': functions_version},
            {'name': 'FUNCTIONS_WORKER_RUNTIME', 'value': worker_runtime},
            {'name': 'WEBSITE_RUN_FROM_PACKAGE', 'value': '1'},
            {'name': 'AzureWebJobsStorage__accountName', 'value': storage_name},
        ]

        if enable_app_insights and self.app_insights:
            app_settings.append(
                {'name': 'APPINSIGHTS_INSTRUMENTATIONKEY', 'value': self.app_insights.instrumentation_key}
            )
            app_settings.append(
                {'name': 'APPLICATIONINSIGHTS_CONNECTION_STRING', 'value': self.app_insights.connection_string}
            )

        self.function_app = factory.create(
            'azure-native:web:WebApp', func_name,
            name=func_name,
            resource_group_name=self.resource_group.name,
            location=location,
            server_farm_id=self.app_service_plan.id,
            kind='functionapp,linux',
            https_only=True,
            identity={
                'type': 'UserAssigned',
                'user_assigned_identities': [self.identity.id],
            },
            site_config={
                'linux_fx_version': '',
                'app_settings': app_settings,
                'ftps_state': 'Disabled',
                'min_tls_version': '1.2',
            },
            tags=tags,
        )

        # =================================================================
        # Exports (Rule #2, #7)
        # =================================================================

        pulumi.export('resource_group_name', rg_name)
        pulumi.export('function_app_name', func_name)
        pulumi.export('function_app_id', self.function_app.id)
        pulumi.export('function_app_url', pulumi.Output.concat('https://', func_name, '.azurewebsites.net'))
        pulumi.export('storage_account_name', storage_name)
        pulumi.export('storage_account_id', self.storage_account.id)
        pulumi.export('identity_id', self.identity.id)
        pulumi.export('identity_principal_id', self.identity.principal_id)
        pulumi.export('app_service_plan_id', self.app_service_plan.id)
        pulumi.export('deployment_mode', 'brownfield' if existing_rg else 'greenfield')
        pulumi.export('environment', env)

        if enable_app_insights and self.app_insights:
            pulumi.export('app_insights_key', self.app_insights.instrumentation_key)
            pulumi.export('app_insights_connection_string', self.app_insights.connection_string)

        if team_name:
            pulumi.export('team_name', team_name)

        return self.get_outputs()

    def get_outputs(self) -> Dict[str, Any]:
        """Get outputs for downstream templates"""
        return {
            'resource_group_name': self.resource_group.name if self.resource_group else None,
            'function_app_name': self.function_app.name if self.function_app else None,
            'function_app_id': self.function_app.id if self.function_app else None,
            'storage_account_name': self.storage_account.name if self.storage_account else None,
            'storage_account_id': self.storage_account.id if self.storage_account else None,
            'identity_id': self.identity.id if self.identity else None,
            'identity_principal_id': self.identity.principal_id if self.identity else None,
            'app_service_plan_id': self.app_service_plan.id if self.app_service_plan else None,
            'app_insights_key': self.app_insights.instrumentation_key if self.app_insights else None,
        }

    @classmethod
    def get_metadata(cls) -> Dict[str, Any]:
        """Template metadata for catalog UI"""
        return {
            "name": "azure-functions-nonprod",
            "title": "Functions Stack",
            "description": "Serverless compute with consumption pricing. Function App + Storage Account + Application Insights + managed identity. For dev/staging event-driven workloads.",
            "category": "serverless",
            "version": "2.0.0",
            "author": "Archie",
            "cloud": "azure",
            "environment": "nonprod",
            "base_cost": "$0-5/month",
            "features": [
                "Function App on Consumption plan (pay per execution)",
                "Storage Account with TLS 1.2 and no public blob access",
                "Application Insights for monitoring and telemetry",
                "User-Assigned Managed Identity for secure access",
                "Support for Node.js, Python, .NET, Java, and PowerShell",
                "HTTPS-only enforcement with TLS 1.2 minimum",
                "FTPS disabled for security",
                "Deploy into existing resource group (brownfield)",
            ],
            "tags": ["azure", "serverless", "functions", "nonprod", "consumption"],
            "deployment_time": "3-5 minutes",
            "complexity": "beginner",
            "use_cases": [
                "Event-driven microservices",
                "API backends with low traffic",
                "Scheduled tasks and cron jobs",
                "Webhook processors",
                "Queue and message processing",
            ],
            "pillars": [
                {
                    "title": "Security",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Managed identity, HTTPS-only, TLS 1.2, and FTPS disabled",
                    "practices": [
                        "User-Assigned Managed Identity eliminates credential storage",
                        "HTTPS-only enforcement for all inbound traffic",
                        "TLS 1.2 minimum on Function App and Storage Account",
                        "FTPS disabled to prevent insecure file transfer",
                        "Public blob access disabled on Storage Account",
                    ]
                },
                {
                    "title": "Operational Excellence",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Application Insights monitoring with automated provisioning",
                    "practices": [
                        "Application Insights for real-time telemetry and diagnostics",
                        "Infrastructure as Code with Pulumi for repeatable deployments",
                        "Standard resource naming and tagging conventions",
                        "Run-from-package deployment for faster cold starts",
                        "Brownfield support for existing resource groups",
                    ]
                },
                {
                    "title": "Reliability",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Azure-managed serverless platform with automatic scaling",
                    "practices": [
                        "Consumption plan auto-scales to match incoming traffic",
                        "Azure-managed infrastructure with built-in redundancy",
                        "Storage Account provides durable trigger state",
                        "Automatic retry for failed function executions",
                    ]
                },
                {
                    "title": "Cost Optimization",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Pay-per-execution with no cost during idle periods",
                    "practices": [
                        "Consumption plan: first 1M executions free per month",
                        "Pay only for compute time used (per-second billing)",
                        "No cost when functions are not executing",
                        "Standard_LRS storage minimizes storage costs",
                        "Per-GB App Insights pricing with low non-prod volume",
                    ]
                },
                {
                    "title": "Sustainability",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Serverless eliminates idle resource consumption entirely",
                    "practices": [
                        "Zero compute resources consumed when idle",
                        "Shared infrastructure maximizes datacenter utilization",
                        "Automatic scale-to-zero reduces energy waste",
                        "Per-execution billing incentivizes efficient code",
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
                    "description": "Used in resource naming (resource group, function app, storage, etc.)",
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
                "runtime": {
                    "type": "string",
                    "default": "node",
                    "title": "Function Runtime",
                    "description": "Programming language runtime for the Function App",
                    "enum": ["node", "python", "dotnet", "java", "powershell"],
                    "order": 10,
                    "group": "Function Configuration",
                },
                "runtime_version": {
                    "type": "string",
                    "default": "18",
                    "title": "Runtime Version",
                    "description": "Version of the runtime (e.g. 18 for Node, 3.11 for Python)",
                    "order": 11,
                    "group": "Function Configuration",
                },
                "functions_version": {
                    "type": "string",
                    "default": "~4",
                    "title": "Functions Extension Version",
                    "description": "Azure Functions runtime version",
                    "enum": ["~4"],
                    "order": 12,
                    "group": "Function Configuration",
                },
                "enable_app_insights": {
                    "type": "boolean",
                    "default": True,
                    "title": "Enable Application Insights",
                    "description": "Deploy Application Insights for monitoring and telemetry",
                    "order": 20,
                    "group": "Architecture Decisions",
                    "cost_impact": "+$0-5/month (per-GB ingestion)",
                },
                "existing_resource_group": {
                    "type": "string",
                    "default": "",
                    "title": "Existing Resource Group",
                    "description": "Deploy into an existing resource group (brownfield). Leave blank to create new.",
                    "order": 30,
                    "group": "Network Configuration",
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
