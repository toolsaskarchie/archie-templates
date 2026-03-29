import pulumi
import pulumi_azure_native as azure
from provisioner.templates.base import InfrastructureTemplate, template_registry
from provisioner.utils.azure import ResourceNamer, get_standard_tags
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory

@template_registry("azure-webapp-network")
class AzureWebAppNetwork(InfrastructureTemplate):
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
        tags = get_standard_tags(project=project, environment=env, template='azure-webapp-network')

        self.resource_group = factory.create('azure:core:ResourceGroup', f'rg-{project}-{env}', {
            'location': location,
            'tags': {**tags, 'Team': 'platform', 'ManagedBy': 'terraform'}
        })

        self.virtual_network = factory.create('azure:network:VirtualNetwork', f'vnet-{project}-{env}', {
            'location': location,
            'resourceGroupName': self.resource_group.name,
            'addressSpace': {'addressPrefixes': ['10.0.0.0/16']},
            'tags': self.resource_group.tags
        })

        self.subnet = factory.create('azure:network:Subnet', f'snet-app-{project}-{env}', {
            'resourceGroupName': self.resource_group.name,
            'virtualNetworkName': self.virtual_network.name,
            'addressPrefixes': ['10.0.1.0/24']
        })

        self.network_security_group = factory.create('azure:network:NetworkSecurityGroup', f'nsg-app-{project}-{env}', {
            'location': location,
            'resourceGroupName': self.resource_group.name,
            'securityRules': [{
                'name': 'AllowHTTPS',
                'priority': 100,
                'direction': 'Inbound',
                'access': 'Allow',
                'protocol': 'Tcp',
                'sourcePortRange': '*',
                'destinationPortRange': '443',
                'sourceAddressPrefix': '*',
                'destinationAddressPrefix': '*'
            }],
            'tags': self.resource_group.tags
        })

        pulumi.export('resource_group_name', self.resource_group.name)
        pulumi.export('virtual_network_id', self.virtual_network.id)
        pulumi.export('subnet_id', self.subnet.id)
        pulumi.export('network_security_group_id', self.network_security_group.id)

        return self.get_outputs()

    def get_outputs(self):
        return {
            'resource_group_name': self.resource_group.name if hasattr(self, 'resource_group') else None,
            'virtual_network_id': self.virtual_network.id if hasattr(self, 'virtual_network') else None,
            'subnet_id': self.subnet.id if hasattr(self, 'subnet') else None,
            'network_security_group_id': self.network_security_group.id if hasattr(self, 'network_security_group') else None
        }

    @classmethod
    def get_metadata(cls):
        return {
            'name': 'azure-webapp-network',
            'title': 'Azure Web App Networking',
            'description': 'Creates a resource group, virtual network, subnet, and network security group for a web application',
            'category': 'networking',
            'cloud': 'azure',
            'tier': 'standard'
        }
