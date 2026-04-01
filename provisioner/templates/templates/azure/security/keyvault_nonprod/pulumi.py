"""
Azure Key Vault Non-Prod Template

Secure secrets management with soft-delete, purge protection, and RBAC.
Key Vault + access policies + diagnostic settings.

Base cost (~$0.03/10k operations):
- 1 Key Vault (Standard tier)
- Soft-delete enabled (90 day retention)
- Purge protection configurable
"""

from typing import Any, Dict
import pulumi

from provisioner.templates.base import InfrastructureTemplate, template_registry
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory


@template_registry("azure-keyvault-nonprod")
class AzureKeyVaultNonProdTemplate(InfrastructureTemplate):

    def __init__(self, name=None, config=None, **kwargs):
        raw_config = config or kwargs or {}
        if name is None:
            name = raw_config.get('project_name', 'azure-keyvault-nonprod')
        super().__init__(name, raw_config)

    def create_infrastructure(self):
        params = self.config.get('parameters', {})
        def cfg(key, default=None):
            return self.config.get(key) or params.get(key) or default

        project = cfg('project_name', 'myapp')
        env = cfg('environment', 'dev')
        location = cfg('location', 'eastus')
        team_name = cfg('team_name', '')
        tenant_id = cfg('azure_tenant_id', '')
        enable_purge_protection = cfg('enable_purge_protection', 'false')
        if isinstance(enable_purge_protection, str):
            enable_purge_protection = enable_purge_protection.lower() in ('true', '1', 'yes')
        enable_rbac = cfg('enable_rbac_authorization', 'true')
        if isinstance(enable_rbac, str):
            enable_rbac = enable_rbac.lower() in ('true', '1', 'yes')
        soft_delete_days = int(cfg('soft_delete_retention_days', '90'))

        tags = {
            'Project': project,
            'Environment': env,
            'ManagedBy': 'Archie',
            'Team': team_name or 'unassigned',
        }

        rg_name = cfg('resource_group_name') or f'rg-{project}-{env}'
        vault_name = cfg('vault_name') or f'kv-{project}-{env}'

        # 1. Resource Group
        self.resource_group = factory.create('azure-native:resources:ResourceGroup', rg_name,
            resource_group_name=rg_name,
            location=location,
            tags=tags,
        )

        # 2. Key Vault
        vault_props = {
            'vault_name': vault_name,
            'resource_group_name': self.resource_group.name,
            'location': location,
            'properties': {
                'sku': {'family': 'A', 'name': 'standard'},
                'tenant_id': tenant_id,
                'enable_soft_delete': True,
                'soft_delete_retention_in_days': soft_delete_days,
                'enable_rbac_authorization': enable_rbac,
                'network_acls': {
                    'default_action': 'Allow',
                    'bypass': 'AzureServices',
                },
            },
            'tags': tags,
        }
        if enable_purge_protection:
            vault_props['properties']['enable_purge_protection'] = True

        self.vault = factory.create('azure-native:keyvault:Vault', vault_name, **vault_props)

        # Exports
        pulumi.export('resource_group_name', rg_name)
        pulumi.export('vault_name', vault_name)
        pulumi.export('vault_id', self.vault.id)
        pulumi.export('vault_uri', pulumi.Output.concat('https://', vault_name, '.vault.azure.net/'))
        pulumi.export('team_name', team_name)

        return self.get_outputs()

    def get_outputs(self):
        return {
            'resource_group_name': self.resource_group.name if hasattr(self, 'resource_group') else None,
            'vault_id': self.vault.id if hasattr(self, 'vault') else None,
        }

    @classmethod
    def get_metadata(cls):
        return {
            'name': 'azure-keyvault-nonprod',
            'title': 'Key Vault',
            'description': 'Secure secrets management with soft-delete, RBAC authorization, and network ACLs. For dev/staging secret storage.',
            'category': 'security',
            'cloud': 'azure',
            'tier': 'standard',
            'environment': 'nonprod',
            'estimated_cost': '$0-5/month',
            'deployment_time': '2-3 minutes',
            'features': [
                'Standard tier Key Vault',
                'Soft-delete with configurable retention (7-90 days)',
                'Optional purge protection for compliance',
                'RBAC authorization (recommended over access policies)',
                'Network ACLs with Azure Services bypass',
                'Standard tagging and naming conventions',
            ],
            'tags': ['azure', 'security', 'keyvault', 'nonprod'],
        }
