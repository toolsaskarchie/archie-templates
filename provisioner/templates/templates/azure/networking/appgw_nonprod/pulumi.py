"""
Azure Application Gateway Non-Prod Template

Azure's L7 load balancer (equivalent to AWS ALB).
Creates VNet + Application Gateway + backend VMs.

Base cost (~$90-130/mo):
- Application Gateway Standard_v2 (~$60/mo base + capacity units)
- Public IP Standard (~$3/mo)
- 2x Standard_B2s VMs (~$60/mo)
- VNet + NSGs (free)
"""

from typing import Any, Dict, Optional
import pulumi

from provisioner.templates.base import InfrastructureTemplate, template_registry
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory


@template_registry("azure-appgw-nonprod")
class AzureAppGatewayNonProdTemplate(InfrastructureTemplate):

    def __init__(self, name=None, config=None, **kwargs):
        raw_config = config or kwargs or {}
        if name is None:
            name = raw_config.get('project_name', 'azure-appgw-nonprod')
        super().__init__(name, raw_config)

    def create_infrastructure(self):
        params = self.config.get('parameters', {})
        def cfg(key, default=None):
            return self.config.get(key) or params.get(key) or default

        project = cfg('project_name', 'myproject')
        env = cfg('environment', 'dev')
        location = cfg('location', 'eastus')
        vnet_cidr = cfg('vnet_cidr', '10.0.0.0/16')
        appgw_cidr = cfg('appgw_subnet_cidr', '10.0.1.0/24')
        backend_cidr = cfg('backend_subnet_cidr', '10.0.2.0/24')
        vm_size = cfg('vm_size', 'Standard_B2s')
        instance_count = int(cfg('instance_count', '2'))
        backend_port = int(cfg('backend_port', '80'))

        tags = {'Project': project, 'Environment': env, 'ManagedBy': 'Archie'}

        # 1. Resource Group
        rg_name = cfg('resource_group_name') or f'rg-{project}-{env}'
        self.resource_group = factory.create('azure-native:resources:ResourceGroup', rg_name,
            resource_group_name=rg_name, location=location, tags=tags,
        )

        # 2. Virtual Network
        vnet_name = cfg('vnet_name') or f'vnet-{project}-{env}'
        self.vnet = factory.create('azure-native:network:VirtualNetwork', vnet_name,
            virtual_network_name=vnet_name,
            resource_group_name=self.resource_group.name,
            location=location,
            address_space={'address_prefixes': [vnet_cidr]},
            tags=tags,
        )

        # 3. App Gateway Subnet (dedicated — no other resources allowed)
        appgw_subnet_name = cfg('appgw_subnet_name') or f'snet-appgw-{project}-{env}'
        self.appgw_subnet = factory.create('azure-native:network:Subnet', appgw_subnet_name,
            subnet_name=appgw_subnet_name,
            resource_group_name=self.resource_group.name,
            virtual_network_name=self.vnet.name,
            address_prefix=appgw_cidr,
        )

        # 4. Backend Subnet + NSG
        backend_nsg_name = cfg('backend_nsg_name') or f'nsg-backend-{project}-{env}'
        self.backend_nsg = factory.create('azure-native:network:NetworkSecurityGroup', backend_nsg_name,
            network_security_group_name=backend_nsg_name,
            resource_group_name=self.resource_group.name,
            location=location,
            security_rules=[
                {
                    'name': 'AllowAppGateway',
                    'priority': 100,
                    'direction': 'Inbound',
                    'access': 'Allow',
                    'protocol': 'Tcp',
                    'source_port_range': '*',
                    'destination_port_range': str(backend_port),
                    'source_address_prefix': appgw_cidr,
                    'destination_address_prefix': '*',
                },
                {
                    'name': 'AllowAzureLoadBalancer',
                    'priority': 110,
                    'direction': 'Inbound',
                    'access': 'Allow',
                    'protocol': '*',
                    'source_port_range': '*',
                    'destination_port_range': '*',
                    'source_address_prefix': 'AzureLoadBalancer',
                    'destination_address_prefix': '*',
                },
            ],
            tags=tags,
        )

        backend_subnet_name = cfg('backend_subnet_name') or f'snet-backend-{project}-{env}'
        self.backend_subnet = factory.create('azure-native:network:Subnet', backend_subnet_name,
            subnet_name=backend_subnet_name,
            resource_group_name=self.resource_group.name,
            virtual_network_name=self.vnet.name,
            address_prefix=backend_cidr,
            network_security_group={'id': self.backend_nsg.id},
        )

        # 5. Public IP for App Gateway
        pip_name = cfg('appgw_pip_name') or f'pip-appgw-{project}-{env}'
        self.appgw_pip = factory.create('azure-native:network:PublicIPAddress', pip_name,
            public_ip_address_name=pip_name,
            resource_group_name=self.resource_group.name,
            location=location,
            sku={'name': 'Standard'},
            public_ip_allocation_method='Static',
            tags=tags,
        )

        # 6. Backend VMs
        self.vms = []
        self.nics = []
        for i in range(1, instance_count + 1):
            nic_name = cfg(f'nic_backend_{i}_name') or f'nic-backend-{project}-{env}-{i}'
            nic = factory.create('azure-native:network:NetworkInterface', nic_name,
                network_interface_name=nic_name,
                resource_group_name=self.resource_group.name,
                location=location,
                ip_configurations=[{
                    'name': 'ipconfig1',
                    'subnet': {'id': self.backend_subnet.id},
                    'private_ip_allocation_method': 'Dynamic',
                }],
                tags=tags,
            )
            self.nics.append(nic)

            vm_name = cfg(f'vm_backend_{i}_name') or f'vm-backend-{project}-{env}-{i}'
            vm = factory.create('azure-native:compute:VirtualMachine', vm_name,
                vm_name=vm_name,
                resource_group_name=self.resource_group.name,
                location=location,
                hardware_profile={'vm_size': vm_size},
                network_profile={
                    'network_interfaces': [{'id': nic.id, 'primary': True}],
                },
                os_profile={
                    'computer_name': f'backend{i}',
                    'admin_username': 'azureuser',
                    'linux_configuration': {
                        'disable_password_authentication': False,
                    },
                },
                storage_profile={
                    'image_reference': {
                        'publisher': 'Canonical',
                        'offer': '0001-com-ubuntu-server-jammy',
                        'sku': '22_04-lts-gen2',
                        'version': 'latest',
                    },
                    'os_disk': {
                        'name': f'osdisk-backend-{project}-{env}-{i}',
                        'create_option': 'FromImage',
                        'managed_disk': {'storage_account_type': 'Standard_LRS'},
                    },
                },
                identity={'type': 'SystemAssigned'},
                tags={**tags, 'Role': 'backend'},
            )
            self.vms.append(vm)

        # 7. Application Gateway
        appgw_name = cfg('appgw_name') or f'appgw-{project}-{env}'
        backend_addresses = [{'ip_address': nic.ip_configurations.apply(lambda ips: ips[0].private_ip_address)} for nic in self.nics]

        self.appgw = factory.create('azure-native:network:ApplicationGateway', appgw_name,
            application_gateway_name=appgw_name,
            resource_group_name=self.resource_group.name,
            location=location,
            sku={
                'name': 'Standard_v2',
                'tier': 'Standard_v2',
                'capacity': 1,
            },
            gateway_ip_configurations=[{
                'name': 'appGatewayIpConfig',
                'subnet': {'id': self.appgw_subnet.id},
            }],
            frontend_ip_configurations=[{
                'name': 'appGatewayFrontendIP',
                'public_ip_address': {'id': self.appgw_pip.id},
            }],
            frontend_ports=[{
                'name': 'port_80',
                'port': 80,
            }],
            backend_address_pools=[{
                'name': 'backendPool',
            }],
            backend_http_settings_collection=[{
                'name': 'httpSettings',
                'port': backend_port,
                'protocol': 'Http',
                'cookie_based_affinity': 'Disabled',
                'request_timeout': 30,
            }],
            http_listeners=[{
                'name': 'httpListener',
                'frontend_ip_configuration': {
                    'id': pulumi.Output.concat(
                        '/subscriptions/', self.resource_group.id.apply(lambda id: id.split('/')[2]),
                        '/resourceGroups/', self.resource_group.name,
                        '/providers/Microsoft.Network/applicationGateways/', appgw_name,
                        '/frontendIPConfigurations/appGatewayFrontendIP'
                    ),
                },
                'frontend_port': {
                    'id': pulumi.Output.concat(
                        '/subscriptions/', self.resource_group.id.apply(lambda id: id.split('/')[2]),
                        '/resourceGroups/', self.resource_group.name,
                        '/providers/Microsoft.Network/applicationGateways/', appgw_name,
                        '/frontendPorts/port_80'
                    ),
                },
                'protocol': 'Http',
            }],
            request_routing_rules=[{
                'name': 'routingRule',
                'rule_type': 'Basic',
                'priority': 100,
                'http_listener': {
                    'id': pulumi.Output.concat(
                        '/subscriptions/', self.resource_group.id.apply(lambda id: id.split('/')[2]),
                        '/resourceGroups/', self.resource_group.name,
                        '/providers/Microsoft.Network/applicationGateways/', appgw_name,
                        '/httpListeners/httpListener'
                    ),
                },
                'backend_address_pool': {
                    'id': pulumi.Output.concat(
                        '/subscriptions/', self.resource_group.id.apply(lambda id: id.split('/')[2]),
                        '/resourceGroups/', self.resource_group.name,
                        '/providers/Microsoft.Network/applicationGateways/', appgw_name,
                        '/backendAddressPools/backendPool'
                    ),
                },
                'backend_http_settings': {
                    'id': pulumi.Output.concat(
                        '/subscriptions/', self.resource_group.id.apply(lambda id: id.split('/')[2]),
                        '/resourceGroups/', self.resource_group.name,
                        '/providers/Microsoft.Network/applicationGateways/', appgw_name,
                        '/backendHttpSettingsCollection/httpSettings'
                    ),
                },
            }],
            tags=tags,
        )

        # Exports — Rule #7: export all generated names for upgrade reuse
        pulumi.export('resource_group_name', rg_name)
        pulumi.export('vnet_name', vnet_name)
        pulumi.export('vnet_id', self.vnet.id)
        pulumi.export('appgw_subnet_name', appgw_subnet_name)
        pulumi.export('backend_subnet_name', backend_subnet_name)
        pulumi.export('backend_nsg_name', backend_nsg_name)
        pulumi.export('appgw_pip_name', pip_name)
        pulumi.export('appgw_name', appgw_name)
        pulumi.export('appgw_id', self.appgw.id)
        pulumi.export('appgw_public_ip', self.appgw_pip.ip_address)
        pulumi.export('appgw_url', self.appgw_pip.ip_address.apply(lambda ip: f'http://{ip}'))
        pulumi.export('backend_subnet_id', self.backend_subnet.id)
        for i in range(instance_count):
            pulumi.export(f'nic_backend_{i}_name', cfg(f'nic_backend_{i}_name') or f'nic-backend-{project}-{env}-{i}')
            pulumi.export(f'vm_backend_{i}_name', cfg(f'vm_backend_{i}_name') or f'vm-backend-{project}-{env}-{i}')

        return self.get_outputs()

    def get_outputs(self):
        return {
            'resource_group_name': self.resource_group.name if hasattr(self, 'resource_group') else None,
            'appgw_id': self.appgw.id if hasattr(self, 'appgw') else None,
            'appgw_public_ip': self.appgw_pip.ip_address if hasattr(self, 'appgw_pip') else None,
            'vnet_id': self.vnet.id if hasattr(self, 'vnet') else None,
        }

    @classmethod
    def get_metadata(cls):
        return {
            'name': 'azure-appgw-nonprod',
            'title': 'Application Gateway with Backend VMs',
            'description': 'L7 load balancer with VNet, backend VMs, NSG isolation, and HTTP routing. Azure equivalent of AWS ALB.',
            'category': 'networking',
            'cloud': 'azure',
            'tier': 'standard',
            'environment': 'nonprod',
            'estimated_cost': '$90-130/month',
            'deployment_time': '10-15 minutes',
            'features': [
                'Application Gateway Standard_v2 with HTTP listener',
                'Dedicated App Gateway subnet',
                'Backend VMs with managed identity',
                'NSG isolation — backend only accepts App Gateway traffic',
                'Configurable instance count and VM size',
                'Standard tagging and naming',
            ],
            'tags': ['azure', 'networking', 'load-balancer', 'appgw', 'nonprod'],
        }
