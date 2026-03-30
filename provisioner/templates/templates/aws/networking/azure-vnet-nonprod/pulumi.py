"""
Azure VNet Non-Prod Template - Single Region Cost-Optimized

Cost-optimized networking foundation for non-production Azure environments.
Single region deployment with public and private subnets, NSGs, and optional NAT Gateway.

Base cost (~$35/mo with NAT Gateway):
- 1 Virtual Network with 2 subnets
- 2 Network Security Groups (web + app tiers)
- 1 NAT Gateway + Public IP (optional, ~$32/mo)
- Route Table for private subnet

Optional features:
- NAT Gateway for private subnet outbound (+$32/mo)
- Additional isolated subnet for databases
- DDoS Protection Standard (+$2944/mo)
"""

from typing import Any, Dict, Optional
import pulumi

from provisioner.templates.base import InfrastructureTemplate, template_registry
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory


@template_registry("azure-vnet-nonprod")
class AzureVNetNonProdTemplate(InfrastructureTemplate):

    def __init__(self, name=None, config=None, **kwargs):
        raw_config = config or kwargs or {}
        if name is None:
            name = raw_config.get('project_name', 'azure-vnet-nonprod')
        super().__init__(name, raw_config)

    def create_infrastructure(self):
        # Config helper — check both root and parameters (Rule #6)
        params = self.config.get('parameters', {})
        def cfg(key, default=None):
            return self.config.get(key) or params.get(key) or default

        project = cfg('project_name', 'myproject')
        env = cfg('environment', 'dev')
        location = cfg('location', 'eastus')
        vnet_cidr = cfg('vnet_cidr', '10.0.0.0/16')
        public_cidr = cfg('public_subnet_cidr', '10.0.1.0/24')
        private_cidr = cfg('private_subnet_cidr', '10.0.2.0/24')
        enable_nat = cfg('enable_nat_gateway', 'true')
        enable_ddos = cfg('enable_ddos_protection', 'false')
        if isinstance(enable_nat, str):
            enable_nat = enable_nat.lower() in ('true', '1', 'yes')
        if isinstance(enable_ddos, str):
            enable_ddos = enable_ddos.lower() in ('true', '1', 'yes')
        team_name = cfg('team_name', '')

        tags = {
            'Project': project,
            'Environment': env,
            'ManagedBy': 'Archie',
            'Team': team_name or 'unassigned',
        }

        # Rule #7: Reuse resource names from outputs on upgrade
        rg_name = cfg('resource_group_name') or f'rg-{project}-{env}'
        vnet_name = cfg('vnet_name') or f'vnet-{project}-{env}'
        web_nsg_name = cfg('web_nsg_name') or f'nsg-web-{project}-{env}'
        app_nsg_name = cfg('app_nsg_name') or f'nsg-app-{project}-{env}'
        public_subnet_name = cfg('public_subnet_name') or f'snet-public-{project}-{env}'
        private_subnet_name = cfg('private_subnet_name') or f'snet-private-{project}-{env}'
        pip_name = cfg('nat_pip_name') or f'pip-nat-{project}-{env}'
        nat_name = cfg('nat_gateway_name') or f'nat-{project}-{env}'
        ddos_plan_name = cfg('ddos_plan_name') or f'ddos-{project}-{env}'

        # 1. Resource Group
        self.resource_group = factory.create('azure-native:resources:ResourceGroup', rg_name,
            resource_group_name=rg_name,
            location=location,
            tags=tags,
        )

        # 2. DDoS Protection Plan (optional)
        ddos_protection = None
        if enable_ddos:
            self.ddos_plan = factory.create('azure-native:network:DdosProtectionPlan', ddos_plan_name,
                ddos_protection_plan_name=ddos_plan_name,
                resource_group_name=self.resource_group.name,
                location=location,
                tags=tags,
            )
            ddos_protection = {
                'id': self.ddos_plan.id,
                'enabled': True
            }

        # 3. Virtual Network
        vnet_args = {
            'virtual_network_name': vnet_name,
            'resource_group_name': self.resource_group.name,
            'location': location,
            'address_space': {'address_prefixes': [vnet_cidr]},
            'tags': tags,
        }
        if ddos_protection:
            vnet_args['ddos_protection_plan'] = ddos_protection

        self.vnet = factory.create('azure-native:network:VirtualNetwork', vnet_name, **vnet_args)

        # 4. NSG — Web Tier (HTTP/HTTPS from internet)
        self.web_nsg = factory.create('azure-native:network:NetworkSecurityGroup', web_nsg_name,
            network_security_group_name=web_nsg_name,
            resource_group_name=self.resource_group.name,
            location=location,
            security_rules=[
                {
                    'name': 'AllowHTTP',
                    'priority': 100,
                    'direction': 'Inbound',
                    'access': 'Allow',
                    'protocol': 'Tcp',
                    'source_port_range': '*',
                    'destination_port_range': '80',
                    'source_address_prefix': '*',
                    'destination_address_prefix': '*',
                },
                {
                    'name': 'AllowHTTPS',
                    'priority': 110,
                    'direction': 'Inbound',
                    'access': 'Allow',
                    'protocol': 'Tcp',
                    'source_port_range': '*',
                    'destination_port_range': '443',
                    'source_address_prefix': '*',
                    'destination_address_prefix': '*',
                },
            ],
            tags=tags,
        )

        # 5. NSG — App Tier (no inbound by default — App Gateway adds rules)
        self.app_nsg = factory.create('azure-native:network:NetworkSecurityGroup', app_nsg_name,
            network_security_group_name=app_nsg_name,
            resource_group_name=self.resource_group.name,
            location=location,
            security_rules=[],
            tags=tags,
        )

        # 6. Public Subnet
        self.public_subnet = factory.create('azure-native:network:Subnet', public_subnet_name,
            subnet_name=public_subnet_name,
            resource_group_name=self.resource_group.name,
            virtual_network_name=self.vnet.name,
            address_prefix=public_cidr,
            network_security_group={'id': self.web_nsg.id},
        )

        # 7. Private Subnet
        self.private_subnet = factory.create('azure-native:network:Subnet', private_subnet_name,
            subnet_name=private_subnet_name,
            resource_group_name=self.resource_group.name,
            virtual_network_name=self.vnet.name,
            address_prefix=private_cidr,
            network_security_group={'id': self.app_nsg.id},
            service_endpoints=[
                {'service': 'Microsoft.Storage'},
                {'service': 'Microsoft.Sql'},
                {'service': 'Microsoft.KeyVault'},
            ],
        )

        # 8. NAT Gateway (optional)
        if enable_nat:
            self.nat_pip = factory.create('azure-native:network:PublicIPAddress', pip_name,
                public_ip_address_name=pip_name,
                resource_group_name=self.resource_group.name,
                location=location,
                sku={'name': 'Standard'},
                public_ip_allocation_method='Static',
                tags=tags,
            )

            self.nat_gateway = factory.create('azure-native:network:NatGateway', nat_name,
                nat_gateway_name=nat_name,
                resource_group_name=self.resource_group.name,
                location=location,
                sku={'name': 'Standard'},
                public_ip_addresses=[{'id': self.nat_pip.id}],
                tags=tags,
            )

        # Exports — Rule #7: export all generated names for upgrade reuse
        pulumi.export('team_name', team_name)
        pulumi.export('resource_group_name', rg_name)
        pulumi.export('vnet_name', vnet_name)
        pulumi.export('vnet_id', self.vnet.id)
        pulumi.export('vnet_cidr', vnet_cidr)
        pulumi.export('web_nsg_name', web_nsg_name)
        pulumi.export('app_nsg_name', app_nsg_name)
        pulumi.export('web_nsg_id', self.web_nsg.id)
        pulumi.export('app_nsg_id', self.app_nsg.id)
        pulumi.export('public_subnet_name', public_subnet_name)
        pulumi.export('private_subnet_name', private_subnet_name)
        pulumi.export('public_subnet_id', self.public_subnet.id)
        pulumi.export('private_subnet_id', self.private_subnet.id)
        if enable_nat:
            pulumi.export('nat_pip_name', pip_name)
            pulumi.export('nat_gateway_name', nat_name)
            pulumi.export('nat_gateway_id', self.nat_gateway.id)
            pulumi.export('nat_public_ip', self.nat_pip.ip_address)
        if enable_ddos:
            pulumi.export('ddos_plan_name', ddos_plan_name)
            pulumi.export('ddos_plan_id', self.ddos_plan.id)

        return self.get_outputs()

    def get_outputs(self):
        outputs = {
            'resource_group_name': self.resource_group.name if hasattr(self, 'resource_group') else None,
            'vnet_id': self.vnet.id if hasattr(self, 'vnet') else None,
            'public_subnet_id': self.public_subnet.id if hasattr(self, 'public_subnet') else None,
            'private_subnet_id': self.private_subnet.id if hasattr(self, 'private_subnet') else None,
            'web_nsg_id': self.web_nsg.id if hasattr(self, 'web_nsg') else None,
            'app_nsg_id': self.app_nsg.id if hasattr(self, 'app_nsg') else None,
        }
        if hasattr(self, 'ddos_plan'):
            outputs['ddos_plan_id'] = self.ddos_plan.id
        return outputs

    @classmethod
    def get_metadata(cls):
        return {
            'name': 'azure-vnet-nonprod',
            'title': 'Virtual Network',
            'description': 'Cost-optimized Azure networking with VNet, subnets, NSGs, optional NAT Gateway and DDoS Protection. Single region for dev/staging.',
            'category': 'networking',
            'cloud': 'azure',
            'tier': 'standard',
            'environment': 'nonprod',
            'estimated_cost': '$3-2979/month',
            'deployment_time': '3-5 minutes',
            'features': [
                'Virtual Network with configurable CIDR',
                'Public and private subnets with NSG isolation',
                'Web tier NSG with HTTP/HTTPS rules',
                'Service endpoints for Storage, SQL, Key Vault',
                'Optional NAT Gateway for private subnet outbound',
                'Optional DDoS Protection Standard for enterprise security',
                'Standard tagging and naming conventions',
            ],
            'tags': ['azure', 'networking', 'vnet', 'nonprod', 'ddos'],
        }

    @classmethod
    def get_config_schema(cls):
        return {
            'type': 'object',
            'properties': {
                'project_name': {
                    'type': 'string',
                    'description': 'Project name for resource naming',
                    'default': 'myproject'
                },
                'environment': {
                    'type': 'string',
                    'description': 'Environment (dev, staging, prod)',
                    'default': 'dev'
                },
                'location': {
                    'type': 'string',
                    'description': 'Azure region',
                    'default': 'eastus'
                },
                'vnet_cidr': {
                    'type': 'string',
                    'description': 'CIDR block for the virtual network',
                    'default': '10.0.0.0/16'
                },
                'public_subnet_cidr': {
                    'type': 'string',
                    'description': 'CIDR block for public subnet',
                    'default': '10.0.1.0/24'
                },
                'private_subnet_cidr': {
                    'type': 'string',
                    'description': 'CIDR block for private subnet',
                    'default': '10.0.2.0/24'
                },
                'enable_nat_gateway': {
                    'type': 'string',
                    'description': 'Enable NAT Gateway for private subnet outbound connectivity',
                    'default': 'true',
                    'enum': ['true', 'false']
                },
                'enable_ddos_protection': {
                    'type': 'string',
                    'description': 'Enable DDoS Protection Standard (adds ~$2944/month)',
                    'default': 'false',
                    'enum': ['true', 'false']
                },
                'team_name': {
                    'type': 'string',
                    'description': 'Team responsible for resources',
                    'default': ''
                }
            },
            'required': ['project_name', 'environment']
        }