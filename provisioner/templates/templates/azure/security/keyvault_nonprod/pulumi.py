"""
Azure Key Vault Non-Prod Template

Secure secrets management with RBAC authorization, soft delete,
and optional purge protection for dev/staging environments.

Base cost (~$0-3/mo — per-operation pricing):
- 1 Key Vault (Standard tier)
- RBAC authorization (recommended over access policies)
- Soft delete enabled (configurable retention 7-90 days)
- Optional purge protection for compliance
- Network ACLs with Azure Services bypass
- Optional diagnostic logging
"""

from typing import Any, Dict, Optional
from pathlib import Path
import pulumi
import pulumi_azure_native as azure_native

from provisioner.templates.base import InfrastructureTemplate, template_registry
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory
from provisioner.utils.azure.tags import get_standard_tags, get_key_vault_tags
from provisioner.utils.azure.naming import get_key_vault_name, get_resource_name


@template_registry("azure-keyvault-nonprod")
class AzureKeyVaultNonProdTemplate(InfrastructureTemplate):
    """
    Azure Key Vault Non-Prod Template

    Secure secrets management with RBAC authorization for non-production
    environments. Soft delete and optional purge protection.
    """

    def __init__(self, name: str = None, config: Dict[str, Any] = None, azure_config: Dict[str, Any] = None, **kwargs):
        """Initialize Azure Key Vault Non-Prod template"""
        raw_config = config or azure_config or kwargs or {}

        if name is None:
            name = (
                raw_config.get('project_name') or
                raw_config.get('projectName') or
                raw_config.get('parameters', {}).get('azure', {}).get('project_name') or
                'azure-keyvault-nonprod'
            )

        super().__init__(name, raw_config)
        self.config = raw_config

        # Resource references (populated in create())
        self.resource_group: Optional[object] = None
        self.vault: Optional[object] = None
        self.diagnostic_setting: Optional[object] = None

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
        """Deploy Key Vault infrastructure (implements abstract method)"""
        return self.create()

    def create(self) -> Dict[str, Any]:
        """Deploy complete Azure Key Vault infrastructure"""

        # Read config
        project = self._cfg('project_name', 'myapp')
        env = self._cfg('environment', 'dev')
        location = self._cfg('location', 'eastus')
        team_name = self._cfg('team_name', '')
        tenant_id = self._cfg('azure_tenant_id', '')
        soft_delete_days = int(self._cfg('soft_delete_retention_days', '90'))
        sku_name = self._cfg('sku_name', 'standard')
        network_default_action = self._cfg('network_default_action', 'Allow')

        enable_purge_protection = self._cfg('enable_purge_protection', False)
        if isinstance(enable_purge_protection, str):
            enable_purge_protection = enable_purge_protection.lower() in ('true', '1', 'yes')

        enable_rbac = self._cfg('enable_rbac_authorization', True)
        if isinstance(enable_rbac, str):
            enable_rbac = enable_rbac.lower() in ('true', '1', 'yes')

        enable_diagnostics = self._cfg('enable_diagnostics', False)
        if isinstance(enable_diagnostics, str):
            enable_diagnostics = enable_diagnostics.lower() in ('true', '1', 'yes')

        # Standard tags
        tags = get_standard_tags(project=project, environment=env)
        tags['ManagedBy'] = 'Archie'
        tags['Template'] = 'azure-keyvault-nonprod'
        tags.update(self._cfg('tags', {}))
        if team_name:
            tags['Team'] = team_name

        # Resource names (prefer injected on upgrade — Rule #3)
        rg_name = self._cfg('resource_group_name') or f'rg-{project}-{env}-kv'
        vault_name = self._cfg('vault_name') or get_key_vault_name(project, env)

        # =================================================================
        # LAYER 1: Resource Group
        # =================================================================

        self.resource_group = factory.create(
            'azure-native:resources:ResourceGroup', rg_name,
            resource_group_name=rg_name,
            location=location,
            tags={**tags, 'Purpose': 'key-vault'},
        )

        # =================================================================
        # LAYER 2: Key Vault
        # =================================================================

        vault_properties = {
            'sku': {'family': 'A', 'name': sku_name},
            'tenant_id': tenant_id,
            'enable_soft_delete': True,
            'soft_delete_retention_in_days': soft_delete_days,
            'enable_rbac_authorization': enable_rbac,
            'network_acls': {
                'default_action': network_default_action,
                'bypass': 'AzureServices',
            },
        }

        # Purge protection — once enabled, cannot be disabled
        if enable_purge_protection:
            vault_properties['enable_purge_protection'] = True

        self.vault = factory.create(
            'azure-native:keyvault:Vault', vault_name,
            vault_name=vault_name,
            resource_group_name=self.resource_group.name,
            location=location,
            properties=vault_properties,
            tags=tags,
        )

        # =================================================================
        # LAYER 3: Diagnostic Settings (optional)
        # =================================================================

        if enable_diagnostics:
            la_workspace_name = self._cfg('log_analytics_workspace_name') or f'la-{project}-{env}-kv'

            log_analytics = factory.create(
                'azure-native:operationalinsights:Workspace', la_workspace_name,
                workspace_name=la_workspace_name,
                resource_group_name=self.resource_group.name,
                location=location,
                sku={'name': 'PerGB2018'},
                retention_in_days=30,
                tags=tags,
            )

            self.diagnostic_setting = factory.create(
                'azure-native:insights:DiagnosticSetting', f'{vault_name}-diag',
                name=f'{vault_name}-diagnostics',
                resource_uri=self.vault.id,
                workspace_id=log_analytics.id,
                logs=[{
                    'category': 'AuditEvent',
                    'enabled': True,
                    'retention_policy': {'enabled': True, 'days': 30},
                }],
                metrics=[{
                    'category': 'AllMetrics',
                    'enabled': True,
                    'retention_policy': {'enabled': True, 'days': 30},
                }],
            )

        # =================================================================
        # Exports (Rule #2, #7)
        # =================================================================

        pulumi.export('resource_group_name', rg_name)
        pulumi.export('vault_name', vault_name)
        pulumi.export('vault_id', self.vault.id)
        pulumi.export('vault_uri', pulumi.Output.concat('https://', vault_name, '.vault.azure.net/'))
        pulumi.export('environment', env)
        if team_name:
            pulumi.export('team_name', team_name)

        return self.get_outputs()

    def get_outputs(self) -> Dict[str, Any]:
        """Get outputs for downstream templates"""
        return {
            'resource_group_name': self.resource_group.name if self.resource_group else None,
            'vault_name': self.vault.name if self.vault else None,
            'vault_id': self.vault.id if self.vault else None,
            'vault_uri': self.vault.properties.vault_uri if self.vault else None,
        }

    @classmethod
    def get_metadata(cls) -> Dict[str, Any]:
        """Template metadata for catalog UI"""
        return {
            "name": "azure-keyvault-nonprod",
            "title": "Key Vault (RBAC)",
            "description": "Secure secrets management with RBAC authorization, soft delete, and optional purge protection. Network ACLs with Azure Services bypass. For dev/staging secret storage.",
            "category": "security",
            "version": "2.0.0",
            "author": "Archie",
            "cloud": "azure",
            "environment": "nonprod",
            "base_cost": "$0-3/month",
            "features": [
                "Standard tier Key Vault with per-operation pricing",
                "RBAC authorization (recommended over access policies)",
                "Soft delete with configurable retention (7-90 days)",
                "Optional purge protection for compliance (irreversible)",
                "Network ACLs with Azure Services bypass",
                "Optional diagnostic logging to Log Analytics",
                "Standard tagging and naming conventions",
            ],
            "tags": ["azure", "security", "keyvault", "secrets", "nonprod", "rbac"],
            "deployment_time": "2-3 minutes",
            "complexity": "beginner",
            "use_cases": [
                "Application secret storage (connection strings, API keys)",
                "Certificate management",
                "Encryption key management",
                "Service-to-service authentication secrets",
                "Development and staging secret isolation",
            ],
            "pillars": [
                {
                    "title": "Security",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "RBAC authorization, soft delete, network ACLs, and optional purge protection",
                    "practices": [
                        "RBAC authorization for fine-grained access control",
                        "Soft delete prevents accidental secret destruction",
                        "Optional purge protection for compliance requirements",
                        "Network ACLs restrict access with Azure Services bypass",
                        "TLS-only access via vault URI",
                    ]
                },
                {
                    "title": "Operational Excellence",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Infrastructure as code with optional diagnostic logging",
                    "practices": [
                        "Infrastructure as Code with Pulumi for repeatable deployments",
                        "Standard resource naming and tagging conventions",
                        "Vault URI exported for easy application integration",
                        "Optional AuditEvent diagnostic logging to Log Analytics",
                        "Configurable retention policies",
                    ]
                },
                {
                    "title": "Reliability",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Azure-managed service with built-in redundancy and soft delete recovery",
                    "practices": [
                        "Azure-managed with 99.99% SLA",
                        "Soft delete allows recovery of accidentally deleted secrets",
                        "Geo-replicated within Azure paired regions",
                        "Automatic failover handled by Azure platform",
                    ]
                },
                {
                    "title": "Cost Optimization",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Per-operation pricing with near-zero cost for non-production workloads",
                    "practices": [
                        "Standard tier at $0.03 per 10,000 operations",
                        "No fixed monthly cost — pay only for operations",
                        "Software keys included at no additional cost",
                        "Minimal cost for dev/test usage patterns",
                    ]
                },
                {
                    "title": "Sustainability",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Shared Azure platform minimizes per-tenant resource consumption",
                    "practices": [
                        "Multi-tenant Azure service with shared infrastructure",
                        "No dedicated compute resources provisioned",
                        "Per-operation model incentivizes efficient secret access patterns",
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
                    "description": "Used in resource naming (resource group, vault name)",
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
                "azure_tenant_id": {
                    "type": "string",
                    "default": "",
                    "title": "Azure Tenant ID",
                    "description": "Azure AD tenant ID for Key Vault (required for access policies, optional for RBAC)",
                    "order": 10,
                    "group": "Vault Configuration",
                },
                "sku_name": {
                    "type": "string",
                    "default": "standard",
                    "title": "Key Vault SKU",
                    "description": "Vault pricing tier (standard or premium for HSM-backed keys)",
                    "enum": ["standard", "premium"],
                    "order": 11,
                    "group": "Vault Configuration",
                    "cost_impact": "Standard ~$0.03/10k ops, Premium ~$1/key/mo for HSM",
                },
                "enable_rbac_authorization": {
                    "type": "boolean",
                    "default": True,
                    "title": "Enable RBAC Authorization",
                    "description": "Use Azure RBAC for data plane access (recommended over access policies)",
                    "order": 20,
                    "group": "Security & Access",
                },
                "enable_purge_protection": {
                    "type": "boolean",
                    "default": False,
                    "title": "Enable Purge Protection",
                    "description": "Prevent purging of soft-deleted secrets (cannot be disabled once enabled)",
                    "order": 21,
                    "group": "Security & Access",
                },
                "soft_delete_retention_days": {
                    "type": "number",
                    "default": 90,
                    "title": "Soft Delete Retention (days)",
                    "description": "Number of days soft-deleted items are retained before permanent deletion",
                    "enum": [7, 14, 30, 60, 90],
                    "order": 22,
                    "group": "Security & Access",
                },
                "network_default_action": {
                    "type": "string",
                    "default": "Allow",
                    "title": "Network Default Action",
                    "description": "Default network ACL action (Allow = open, Deny = restricted to allowed IPs/VNets)",
                    "enum": ["Allow", "Deny"],
                    "order": 23,
                    "group": "Security & Access",
                },
                "enable_diagnostics": {
                    "type": "boolean",
                    "default": False,
                    "title": "Enable Diagnostic Logging",
                    "description": "Deploy Log Analytics workspace and enable AuditEvent logging",
                    "order": 30,
                    "group": "Architecture Decisions",
                    "cost_impact": "+$2-5/month (per-GB ingestion)",
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
