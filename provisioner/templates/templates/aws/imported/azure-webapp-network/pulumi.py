import pulumi
import pulumi_azure as azure
from provisioner.templates.base import InfrastructureTemplate, template_registry
from provisioner.utils.aws import ResourceNamer, get_standard_tags
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory

@template_registry("azure-webapp-network")
class AzureWebappNetwork(InfrastructureTemplate):
    def __init__(self, name=None, config=None, **kwargs):
        raw_config = config or kwargs or {}
        if name is None:
            name = raw_config.get('project_name', 'azure-webapp-network')
        super().__init__(name, raw_config)

    def create_infrastructure(self):
        params = self.config.get('parameters', {})
        def cfg(key, default=None):
            return self.config.get(key) or params.get(key) or default

        project = cfg('project_name', 'webapp')
        env = cfg('environment', 'dev')
        location = cfg('location', 'East US 2')
        tags = {
            'Environment': env,
            'Team': 'platform',
            'ManagedBy': 'pulumi'
        }

        self.resource_group = factory.create('azure:resources:ResourceGroup', f'rg-{project}-{env}',
            name=f'rg-{project}-{env}',
            location=location,
            tags=tags
        )

        self.virtual_network = factory.create('azure:network:VirtualNetwork', f'vnet-{project}-{env}',
            name=f'vnet-{project}-{env}',
            resource_group_name=self.resource_group.name,
            location=location,
            address_spaces=['10.0.0.0/16'],
            tags=tags
        )

        self.subnet = factory.create('azure:network:Subnet', f'snet-{project}-{env}',
            name='snet-app',
            resource_group_name=self.resource_group.name,
            virtual_network_name=self.virtual_network.name,
            address_prefixes=['10.0.1.0/24']
        )

        self.network_security_group = factory.create('azure:network:NetworkSecurityGroup', f'nsg-{project}-{env}',
            name=f'nsg-{project}-{env}',
            resource_group_name=self.resource_group.name,
            location=location,
            security_rules=[
                {
                    'name': 'AllowHTTPS',
                    'priority': 100,
                    'direction': 'Inbound',
                    'access': 'Allow',
                    'protocol': 'Tcp',
                    'source_port_range': '*',
                    'destination_port_range': '443',
                    'source_address_prefix': '*',
                    'destination_address_prefix': '*'
                }
            ],
            tags=tags
        )

        pulumi.export('resource_group_name', self.resource_group.name)
        pulumi.export('virtual_network_name', self.virtual_network.name)
        pulumi.export('subnet_name', self.subnet.name)
        pulumi.export('network_security_group_name', self.network_security_group.name)

        return self.get_outputs()

    def get_outputs(self):
        return {
            'resource_group_name': self.resource_group.name if hasattr(self, 'resource_group') else None,
            'virtual_network_name': self.virtual_network.name if hasattr(self, 'virtual_network') else None,
            'subnet_name': self.subnet.name if hasattr(self, 'subnet') else None,
            'network_security_group_name': self.network_security_group.name if hasattr(self, 'network_security_group') else None
        }

    @classmethod
    def get_metadata(cls):
        return {
            'name': 'azure-webapp-network',
            'title': 'Azure WebApp Network Infrastructure',
            'description': 'Creates an Azure resource group, virtual network, subnet, and network security group',
            'category': 'networking',
            'cloud': 'azure',
            'tier': 'standard'
        }
