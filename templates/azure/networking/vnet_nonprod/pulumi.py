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
"""

from typing import Any, Dict, Optional
import pulumi
from pulumi import ResourceOptions

from provisioner.templates.base import InfrastructureTemplate, template_registry
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory


@template_registry("azure-vnet-nonprod")
class AzureVNetNonProdTemplate(InfrastructureTemplate):

    def __init__(self, name: str = None, config: Dict[str, Any] = None, azure_config: Dict[str, Any] = None, **kwargs):
        raw_config = config or azure_config or kwargs or {}
        if name is None:
            name = (
                raw_config.get('project_name') or
                raw_config.get('projectName') or
                raw_config.get('parameters', {}).get('azure', {}).get('project_name') or
                'azure-vnet-nonprod'
            )
        super().__init__(name, raw_config)
        self.config = raw_config

        # Resource references (populated in create())
        self.resource_group: Optional[object] = None
        self.vnet: Optional[object] = None
        self.web_nsg: Optional[object] = None
        self.app_nsg: Optional[object] = None
        self.public_subnet: Optional[object] = None
        self.private_subnet: Optional[object] = None
        self.nat_pip: Optional[object] = None
        self.nat_gateway: Optional[object] = None

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
        """Deploy Azure VNet infrastructure (implements abstract method)"""
        return self.create()

    def create(self) -> Dict[str, Any]:
        """Deploy complete Azure VNet infrastructure"""
        project = self._cfg('project_name', 'myproject')
        env = self._cfg('environment', 'dev')
        location = self._cfg('location', 'eastus')
        vnet_cidr = self._cfg('vnet_cidr', '10.0.0.0/16')
        public_cidr = self._cfg('public_subnet_cidr', '10.0.1.0/24')
        private_cidr = self._cfg('private_subnet_cidr', '10.0.2.0/24')
        enable_nat = self._cfg('enable_nat_gateway', 'true')
        if isinstance(enable_nat, str):
            enable_nat = enable_nat.lower() in ('true', '1', 'yes')
        team_name = self._cfg('team_name', '')

        tags = {
            'Project': project,
            'Environment': env,
            'ManagedBy': 'Archie',
        }
        if team_name:
            tags['Team'] = team_name

        # Rule #7: Reuse resource names from outputs on upgrade
        rg_name = self._cfg('resource_group_name') or f'rg-{project}-{env}'
        vnet_name = self._cfg('vnet_name') or f'vnet-{project}-{env}'
        web_nsg_name = self._cfg('web_nsg_name') or f'nsg-web-{project}-{env}'
        app_nsg_name = self._cfg('app_nsg_name') or f'nsg-app-{project}-{env}'
        public_subnet_name = self._cfg('public_subnet_name') or f'snet-public-{project}-{env}'
        private_subnet_name = self._cfg('private_subnet_name') or f'snet-private-{project}-{env}'
        pip_name = self._cfg('nat_pip_name') or f'pip-nat-{project}-{env}'
        nat_name = self._cfg('nat_gateway_name') or f'nat-{project}-{env}'

        # 1. Resource Group
        self.resource_group = factory.create('azure-native:resources:ResourceGroup', rg_name,
            resource_group_name=rg_name,
            location=location,
            tags=tags,
        )

        # 2. Virtual Network
        self.vnet = factory.create('azure-native:network:VirtualNetwork', vnet_name,
            virtual_network_name=vnet_name,
            resource_group_name=self.resource_group.name,
            location=location,
            address_space={'address_prefixes': [vnet_cidr]},
            tags=tags,
        )

        # 3. NSG -- Web Tier (HTTP/HTTPS from internet)
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

        # 4. NSG -- App Tier (no inbound by default -- App Gateway adds rules)
        self.app_nsg = factory.create('azure-native:network:NetworkSecurityGroup', app_nsg_name,
            network_security_group_name=app_nsg_name,
            resource_group_name=self.resource_group.name,
            location=location,
            security_rules=[],
            tags=tags,
        )

        # 5. Public Subnet
        self.public_subnet = factory.create('azure-native:network:Subnet', public_subnet_name,
            subnet_name=public_subnet_name,
            resource_group_name=self.resource_group.name,
            virtual_network_name=self.vnet.name,
            address_prefix=public_cidr,
            network_security_group={'id': self.web_nsg.id},
        )

        # 6. Private Subnet (depends on public subnet -- Azure can't create subnets concurrently)
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
            opts=ResourceOptions(depends_on=[self.public_subnet]),
        )

        # 7. NAT Gateway (optional)
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

        # Exports -- Rule #7: export all generated names for upgrade reuse
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
        pulumi.export('environment', env)
        if enable_nat:
            pulumi.export('nat_pip_name', pip_name)
            pulumi.export('nat_gateway_name', nat_name)
            pulumi.export('nat_gateway_id', self.nat_gateway.id)
            pulumi.export('nat_public_ip', self.nat_pip.ip_address)

        return self.get_outputs()

    def get_outputs(self) -> Dict[str, Any]:
        return {
            'resource_group_name': self.resource_group.name if self.resource_group else None,
            'vnet_id': self.vnet.id if self.vnet else None,
            'vnet_name': self.vnet.name if self.vnet else None,
            'public_subnet_id': self.public_subnet.id if self.public_subnet else None,
            'private_subnet_id': self.private_subnet.id if self.private_subnet else None,
            'web_nsg_id': self.web_nsg.id if self.web_nsg else None,
            'app_nsg_id': self.app_nsg.id if self.app_nsg else None,
            'nat_gateway_id': self.nat_gateway.id if self.nat_gateway else None,
            'nat_public_ip': self.nat_pip.ip_address if self.nat_pip else None,
        }

    @classmethod
    def get_metadata(cls) -> Dict[str, Any]:
        return {
            'name': 'azure-vnet-nonprod',
            'title': 'Virtual Network',
            'description': 'Cost-optimized Azure networking with VNet, subnets, NSGs, and optional NAT Gateway. Single region for dev/staging.',
            'category': 'networking',
            'version': '1.0.0',
            'author': 'Archie',
            'cloud': 'azure',
            'environment': 'nonprod',
            'base_cost': '$3-35/month',
            'deployment_time': '3-5 minutes',
            'complexity': 'beginner',
            'features': [
                'Virtual Network with configurable CIDR',
                'Public and private subnets with NSG isolation',
                'Web tier NSG with HTTP/HTTPS rules',
                'Service endpoints for Storage, SQL, Key Vault',
                'Optional NAT Gateway for private subnet outbound',
                'Standard tagging and naming conventions',
            ],
            'tags': ['azure', 'networking', 'vnet', 'nonprod'],
            'use_cases': [
                'Foundation networking for dev/staging workloads',
                'Isolated environments for development teams',
                'VNet for App Service, Container Apps, or VMs',
                'Testing network security configurations',
            ],
            'pillars': [
                {
                    'title': 'Security',
                    'score': 'good',
                    'score_color': '#10b981',
                    'description': 'Tiered NSGs with web and app separation',
                    'practices': [
                        'Web NSG allows only HTTP/HTTPS from internet',
                        'App NSG blocks all inbound by default',
                        'Service endpoints for Azure PaaS services',
                        'Subnet-level network segmentation',
                    ],
                },
                {
                    'title': 'Operational Excellence',
                    'score': 'good',
                    'score_color': '#10b981',
                    'description': 'Standard naming, tagging, and subnet structure',
                    'practices': [
                        'Consistent resource naming convention',
                        'Standard tagging for cost tracking',
                        'Predictable subnet CIDR allocation',
                    ],
                },
                {
                    'title': 'Cost Optimization',
                    'score': 'excellent',
                    'score_color': '#10b981',
                    'description': 'VNet and NSGs are free, NAT Gateway is optional',
                    'practices': [
                        'VNet and subnets have no base cost',
                        'NAT Gateway is optional (+$32/month)',
                        'Single region reduces data transfer costs',
                    ],
                },
                {
                    'title': 'Reliability',
                    'score': 'needs-improvement',
                    'score_color': '#f59e0b',
                    'description': 'Single region, single NAT Gateway (appropriate for non-prod)',
                    'practices': [
                        'Single region deployment',
                        'NAT Gateway provides outbound connectivity',
                        'Non-prod: multi-AZ not required',
                    ],
                },
                {
                    'title': 'Sustainability',
                    'score': 'good',
                    'score_color': '#10b981',
                    'description': 'Minimal resources, optional NAT Gateway',
                    'practices': [
                        'No over-provisioning of network resources',
                        'Optional NAT Gateway avoids unnecessary cost',
                        'Single region reduces infrastructure footprint',
                    ],
                },
            ],
        }

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'project_name': {
                    'type': 'string',
                    'default': 'myproject',
                    'title': 'Project Name',
                    'description': 'Used in resource naming',
                    'order': 1,
                    'group': 'Essentials',
                    'isEssential': True,
                },
                'environment': {
                    'type': 'string',
                    'default': 'dev',
                    'title': 'Environment',
                    'description': 'Deployment environment',
                    'enum': ['dev', 'staging'],
                    'order': 2,
                    'group': 'Essentials',
                    'isEssential': True,
                },
                'location': {
                    'type': 'string',
                    'default': 'eastus',
                    'title': 'Azure Region',
                    'description': 'Azure region for all resources',
                    'order': 3,
                    'group': 'Essentials',
                    'isEssential': True,
                },
                'vnet_cidr': {
                    'type': 'string',
                    'default': '10.0.0.0/16',
                    'title': 'VNet CIDR',
                    'description': 'Address space for the virtual network',
                    'order': 10,
                    'group': 'Network Configuration',
                },
                'public_subnet_cidr': {
                    'type': 'string',
                    'default': '10.0.1.0/24',
                    'title': 'Public Subnet CIDR',
                    'description': 'Address range for the public subnet',
                    'order': 11,
                    'group': 'Network Configuration',
                },
                'private_subnet_cidr': {
                    'type': 'string',
                    'default': '10.0.2.0/24',
                    'title': 'Private Subnet CIDR',
                    'description': 'Address range for the private subnet',
                    'order': 12,
                    'group': 'Network Configuration',
                },
                'enable_nat_gateway': {
                    'type': 'boolean',
                    'default': True,
                    'title': 'Enable NAT Gateway',
                    'description': 'NAT Gateway for private subnet outbound access',
                    'order': 20,
                    'group': 'Architecture Decisions',
                    'cost_impact': '+$32/month',
                },
                'team_name': {
                    'type': 'string',
                    'default': '',
                    'title': 'Team Name',
                    'description': 'Team that owns this resource',
                    'order': 50,
                    'group': 'Tags',
                },
            },
            'required': ['project_name'],
        }
