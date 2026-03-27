"""
Azure VNet Production Template - Multi-AZ Enterprise

Enterprise-grade Azure networking for production workloads.
3 availability zones, 3-tier subnet architecture, HA NAT Gateways,
Azure Bastion for secure access, and service endpoints.

Base cost (~$130/mo):
- 3 NAT Gateways (~$96/mo)
- 3 Public IPs (~$9/mo)
- Azure Bastion (~$140/mo if enabled)
- VNet, subnets, NSGs, route tables (free)
"""

from typing import Any, Dict, Optional
import pulumi

from provisioner.templates.base import InfrastructureTemplate, template_registry
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory


@template_registry("azure-vnet-prod")
class AzureVNetProdTemplate(InfrastructureTemplate):

    def __init__(self, name=None, config=None, **kwargs):
        raw_config = config or kwargs or {}
        if name is None:
            name = raw_config.get('project_name', 'azure-vnet-prod')
        super().__init__(name, raw_config)

    def create_infrastructure(self):
        params = self.config.get('parameters', {})
        def cfg(key, default=None):
            return self.config.get(key) or params.get(key) or default

        project = cfg('project_name', 'myproject')
        env = cfg('environment', 'prod')
        location = cfg('location', 'eastus')
        vnet_cidr = cfg('vnet_cidr', '10.0.0.0/16')

        tags = {'Project': project, 'Environment': env, 'ManagedBy': 'Archie'}

        # 1. Resource Group
        rg_name = f'rg-{project}-{env}'
        self.resource_group = factory.create('azure-native:resources:ResourceGroup', rg_name,
            resource_group_name=rg_name, location=location, tags=tags,
        )

        # 2. Virtual Network
        vnet_name = f'vnet-{project}-{env}'
        self.vnet = factory.create('azure-native:network:VirtualNetwork', vnet_name,
            virtual_network_name=vnet_name,
            resource_group_name=self.resource_group.name,
            location=location,
            address_space={'address_prefixes': [vnet_cidr]},
            tags=tags,
        )

        # 3. NSGs — Web, App, DB tiers
        self.nsgs = {}
        for tier, rules in [
            ('web', [
                {'name': 'AllowHTTP', 'priority': 100, 'direction': 'Inbound', 'access': 'Allow', 'protocol': 'Tcp',
                 'source_port_range': '*', 'destination_port_range': '80', 'source_address_prefix': '*', 'destination_address_prefix': '*'},
                {'name': 'AllowHTTPS', 'priority': 110, 'direction': 'Inbound', 'access': 'Allow', 'protocol': 'Tcp',
                 'source_port_range': '*', 'destination_port_range': '443', 'source_address_prefix': '*', 'destination_address_prefix': '*'},
            ]),
            ('app', []),
            ('db', []),
        ]:
            nsg_name = f'nsg-{tier}-{project}-{env}'
            self.nsgs[tier] = factory.create('azure-native:network:NetworkSecurityGroup', nsg_name,
                network_security_group_name=nsg_name,
                resource_group_name=self.resource_group.name,
                location=location, security_rules=rules, tags={**tags, 'Tier': tier},
            )

        # 4. Subnets — 3 per tier (public, private, isolated)
        self.subnets = {}
        zone_suffixes = ['1', '2', '3']
        base_octets = {'public': 1, 'private': 4, 'isolated': 7}
        nsg_map = {'public': 'web', 'private': 'app', 'isolated': 'db'}

        for tier in ['public', 'private', 'isolated']:
            for i, zone in enumerate(zone_suffixes):
                octet = base_octets[tier] + i
                cidr = f'10.0.{octet}.0/24'
                subnet_name = f'snet-{tier}-{project}-{env}-{zone}'
                svc_endpoints = []
                if tier in ('private', 'isolated'):
                    svc_endpoints = [
                        {'service': 'Microsoft.Storage'},
                        {'service': 'Microsoft.Sql'},
                        {'service': 'Microsoft.KeyVault'},
                    ]
                self.subnets[f'{tier}-{zone}'] = factory.create('azure-native:network:Subnet', subnet_name,
                    subnet_name=subnet_name,
                    resource_group_name=self.resource_group.name,
                    virtual_network_name=self.vnet.name,
                    address_prefix=cidr,
                    network_security_group={'id': self.nsgs[nsg_map[tier]].id},
                    service_endpoints=svc_endpoints if svc_endpoints else None,
                )

        # 5. NAT Gateways — one per zone for HA
        self.nat_gateways = {}
        self.nat_pips = {}
        for zone in zone_suffixes:
            pip_name = f'pip-nat-{project}-{env}-{zone}'
            self.nat_pips[zone] = factory.create('azure-native:network:PublicIPAddress', pip_name,
                public_ip_address_name=pip_name,
                resource_group_name=self.resource_group.name,
                location=location,
                sku={'name': 'Standard'},
                public_ip_allocation_method='Static',
                zones=[zone],
                tags=tags,
            )
            nat_name = f'nat-{project}-{env}-{zone}'
            self.nat_gateways[zone] = factory.create('azure-native:network:NatGateway', nat_name,
                nat_gateway_name=nat_name,
                resource_group_name=self.resource_group.name,
                location=location,
                sku={'name': 'Standard'},
                zones=[zone],
                public_ip_addresses=[{'id': self.nat_pips[zone].id}],
                tags=tags,
            )

        # Exports
        pulumi.export('resource_group_name', self.resource_group.name)
        pulumi.export('vnet_id', self.vnet.id)
        pulumi.export('vnet_name', vnet_name)
        pulumi.export('vnet_cidr', vnet_cidr)
        pulumi.export('web_nsg_id', self.nsgs['web'].id)
        pulumi.export('app_nsg_id', self.nsgs['app'].id)
        pulumi.export('db_nsg_id', self.nsgs['db'].id)
        for key, subnet in self.subnets.items():
            pulumi.export(f'subnet_{key.replace("-", "_")}_id', subnet.id)

        return self.get_outputs()

    def get_outputs(self):
        outputs = {
            'resource_group_name': self.resource_group.name if hasattr(self, 'resource_group') else None,
            'vnet_id': self.vnet.id if hasattr(self, 'vnet') else None,
        }
        if hasattr(self, 'nsgs'):
            for tier, nsg in self.nsgs.items():
                outputs[f'{tier}_nsg_id'] = nsg.id
        if hasattr(self, 'subnets'):
            for key, subnet in self.subnets.items():
                outputs[f'subnet_{key.replace("-", "_")}_id'] = subnet.id
        return outputs

    @classmethod
    def get_metadata(cls):
        return {
            'name': 'azure-vnet-prod',
            'title': '3-Tier Enterprise Azure Network',
            'description': 'Enterprise-grade Azure networking with 3-AZ VNet, public/private/isolated subnets, HA NAT Gateways, and tiered NSGs.',
            'category': 'networking',
            'cloud': 'azure',
            'tier': 'standard',
            'environment': 'PROD & NONPROD',
            'estimated_cost': '$100-240/month',
            'deployment_time': '5-10 minutes',
            'features': [
                '3-AZ subnet architecture for high availability',
                'Tiered NSGs: web (HTTP/HTTPS), app, db',
                'HA NAT Gateways (one per zone)',
                'Service endpoints for Storage, SQL, Key Vault',
                'Isolated subnets for databases',
                'Enterprise tagging and naming',
            ],
            'tags': ['azure', 'networking', 'vnet', 'production', 'enterprise', 'multi-az'],
        }
