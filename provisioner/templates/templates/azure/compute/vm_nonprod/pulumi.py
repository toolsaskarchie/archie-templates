"""
Azure VM Non-Prod Template

Cost-optimized Azure VM for development and staging.
Creates VNet + NSG + VM with managed identity.

Base cost (~$35-60/mo):
- Standard_B2s VM (~$30/mo)
- 30GB managed disk (~$2/mo)
- Public IP (~$3/mo)
- VNet + NSG (free)
"""

from typing import Any, Dict, Optional
import pulumi

from provisioner.templates.base import InfrastructureTemplate, template_registry
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory


@template_registry("azure-vm-nonprod")
class AzureVMNonProdTemplate(InfrastructureTemplate):

    def __init__(self, name=None, config=None, **kwargs):
        raw_config = config or kwargs or {}
        if name is None:
            name = raw_config.get('project_name', 'azure-vm-nonprod')
        super().__init__(name, raw_config)

    def create_infrastructure(self):
        params = self.config.get('parameters', {})
        def cfg(key, default=None):
            return self.config.get(key) or params.get(key) or default

        project = cfg('project_name', 'myproject')
        env = cfg('environment', 'dev')
        location = cfg('location', 'eastus')
        vm_size = cfg('vm_size', 'Standard_B2s')
        admin_username = cfg('admin_username', 'azureuser')
        ssh_key = cfg('ssh_public_key', '')
        disk_size = int(cfg('disk_size_gb', '30'))
        enable_pip = cfg('enable_public_ip', 'true')
        if isinstance(enable_pip, str):
            enable_pip = enable_pip.lower() in ('true', '1', 'yes')
        ssh_access_ip = cfg('ssh_access_ip', '*')

        tags = {'Project': project, 'Environment': env, 'ManagedBy': 'Archie'}

        # Rule #7: Reuse resource names from outputs on upgrade
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
            address_space={'address_prefixes': ['10.0.0.0/16']},
            tags=tags,
        )

        # 3. Subnet
        subnet_name = cfg('subnet_name') or f'snet-{project}-{env}'
        self.subnet = factory.create('azure-native:network:Subnet', subnet_name,
            subnet_name=subnet_name,
            resource_group_name=self.resource_group.name,
            virtual_network_name=self.vnet.name,
            address_prefix='10.0.1.0/24',
        )

        # 4. NSG with SSH access
        nsg_name = cfg('nsg_name') or f'nsg-{project}-{env}'
        ssh_rules = [
            {
                'name': 'AllowSSH',
                'priority': 100,
                'direction': 'Inbound',
                'access': 'Allow',
                'protocol': 'Tcp',
                'source_port_range': '*',
                'destination_port_range': '22',
                'source_address_prefix': ssh_access_ip,
                'destination_address_prefix': '*',
            },
        ]
        self.nsg = factory.create('azure-native:network:NetworkSecurityGroup', nsg_name,
            network_security_group_name=nsg_name,
            resource_group_name=self.resource_group.name,
            location=location,
            security_rules=ssh_rules,
            tags=tags,
        )

        # 5. Public IP (optional)
        if enable_pip:
            pip_name = cfg('pip_name') or f'pip-{project}-{env}'
            self.public_ip = factory.create('azure-native:network:PublicIPAddress', pip_name,
                public_ip_address_name=pip_name,
                resource_group_name=self.resource_group.name,
                location=location,
                sku={'name': 'Standard'},
                public_ip_allocation_method='Static',
                tags=tags,
            )

        # 6. Network Interface
        nic_name = cfg('nic_name') or f'nic-{project}-{env}'
        ip_config = {
            'name': 'ipconfig1',
            'subnet': {'id': self.subnet.id},
            'private_ip_allocation_method': 'Dynamic',
        }
        if enable_pip:
            ip_config['public_ip_address'] = {'id': self.public_ip.id}

        self.nic = factory.create('azure-native:network:NetworkInterface', nic_name,
            network_interface_name=nic_name,
            resource_group_name=self.resource_group.name,
            location=location,
            ip_configurations=[ip_config],
            network_security_group={'id': self.nsg.id},
            tags=tags,
        )

        # 7. Virtual Machine
        vm_name = cfg('vm_name') or f'vm-{project}-{env}'
        vm_args = {
            'vm_name': vm_name,
            'resource_group_name': self.resource_group.name,
            'location': location,
            'hardware_profile': {'vm_size': vm_size},
            'network_profile': {
                'network_interfaces': [{'id': self.nic.id, 'primary': True}],
            },
            'os_profile': {
                'computer_name': vm_name[:15],
                'admin_username': admin_username,
            },
            'storage_profile': {
                'image_reference': {
                    'publisher': 'Canonical',
                    'offer': '0001-com-ubuntu-server-jammy',
                    'sku': '22_04-lts-gen2',
                    'version': 'latest',
                },
                'os_disk': {
                    'name': f'osdisk-{project}-{env}',
                    'create_option': 'FromImage',
                    'disk_size_gb': disk_size,
                    'managed_disk': {'storage_account_type': 'Standard_LRS'},
                },
            },
            'identity': {'type': 'SystemAssigned'},
            'tags': tags,
        }

        # SSH key or password auth
        if ssh_key:
            vm_args['os_profile']['linux_configuration'] = {
                'disable_password_authentication': True,
                'ssh': {
                    'public_keys': [{
                        'path': f'/home/{admin_username}/.ssh/authorized_keys',
                        'key_data': ssh_key,
                    }],
                },
            }

        self.vm = factory.create('azure-native:compute:VirtualMachine', vm_name, **vm_args)

        # Exports — Rule #7: export all generated names for upgrade reuse
        pulumi.export('resource_group_name', rg_name)
        pulumi.export('vnet_name', vnet_name)
        pulumi.export('vnet_id', self.vnet.id)
        pulumi.export('subnet_name', subnet_name)
        pulumi.export('nsg_name', nsg_name)
        pulumi.export('nic_name', nic_name)
        pulumi.export('vm_name', vm_name)
        pulumi.export('vm_id', self.vm.id)
        pulumi.export('private_ip', self.nic.ip_configurations.apply(lambda ips: ips[0].private_ip_address if ips else ''))
        if enable_pip:
            pulumi.export('pip_name', pip_name)
            pulumi.export('public_ip', self.public_ip.ip_address)
            pulumi.export('ssh_command', self.public_ip.ip_address.apply(
                lambda ip: f'ssh {admin_username}@{ip}' if ip else 'N/A (no public IP)'
            ))

        return self.get_outputs()

    def get_outputs(self):
        return {
            'resource_group_name': self.resource_group.name if hasattr(self, 'resource_group') else None,
            'vm_id': self.vm.id if hasattr(self, 'vm') else None,
            'vnet_id': self.vnet.id if hasattr(self, 'vnet') else None,
            'public_ip': self.public_ip.ip_address if hasattr(self, 'public_ip') else None,
        }

    @classmethod
    def get_metadata(cls):
        return {
            'name': 'azure-vm-nonprod',
            'title': 'Virtual Machine',
            'description': 'Cost-optimized Azure VM with VNet, NSG, managed identity, and optional public IP. For dev/staging workloads.',
            'category': 'compute',
            'cloud': 'azure',
            'tier': 'standard',
            'environment': 'nonprod',
            'estimated_cost': '$35-60/month',
            'deployment_time': '5-8 minutes',
            'features': [
                'Ubuntu 22.04 LTS with configurable VM size',
                'VNet with NSG and SSH access control',
                'Managed identity for Azure RBAC',
                'Optional public IP with static allocation',
                'Managed OS disk with configurable size',
                'Standard tagging and naming',
            ],
            'tags': ['azure', 'compute', 'vm', 'nonprod'],
        }
