"""
Azure VM Non-Prod Template

Cost-optimized Azure VM for development and staging.
Creates VNet + NSG + VM with managed identity.

Base cost (~$35-60/mo):
- Standard_DS1_v2 VM (~$30/mo)
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

    def __init__(self, name: str = None, config: Dict[str, Any] = None, azure_config: Dict[str, Any] = None, **kwargs):
        raw_config = config or azure_config or kwargs or {}
        if name is None:
            name = (
                raw_config.get('project_name') or
                raw_config.get('projectName') or
                raw_config.get('parameters', {}).get('azure', {}).get('project_name') or
                'azure-vm-nonprod'
            )
        super().__init__(name, raw_config)
        self.config = raw_config

        # Resource references (populated in create())
        self.resource_group: Optional[object] = None
        self.vnet: Optional[object] = None
        self.subnet: Optional[object] = None
        self.nsg: Optional[object] = None
        self.public_ip: Optional[object] = None
        self.nic: Optional[object] = None
        self.vm: Optional[object] = None

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
        """Deploy Azure VM infrastructure (implements abstract method)"""
        return self.create()

    def create(self) -> Dict[str, Any]:
        """Deploy complete Azure VM infrastructure"""
        project = self._cfg('project_name', 'myproject')
        env = self._cfg('environment', 'dev')
        location = self._cfg('location', 'centralus')
        vm_size = self._cfg('vm_size', 'Standard_D2s_v3')
        admin_username = self._cfg('admin_username', 'azureuser')
        ssh_key = self._cfg('ssh_public_key', '')
        disk_size = int(self._cfg('disk_size_gb', '30'))
        enable_pip = self._cfg('enable_public_ip', 'true')
        if isinstance(enable_pip, str):
            enable_pip = enable_pip.lower() in ('true', '1', 'yes')
        ssh_access_ip = self._cfg('ssh_access_ip', '*')
        team_name = self._cfg('team_name', '')

        tags = {'Project': project, 'Environment': env, 'ManagedBy': 'Archie'}
        if team_name:
            tags['Team'] = team_name

        # Rule #7: Reuse resource names from outputs on upgrade
        rg_name = self._cfg('resource_group_name') or f'rg-{project}-{env}'
        self.resource_group = factory.create('azure-native:resources:ResourceGroup', rg_name,
            resource_group_name=rg_name, location=location, tags=tags,
        )

        # 2. Virtual Network
        vnet_name = self._cfg('vnet_name') or f'vnet-{project}-{env}'
        self.vnet = factory.create('azure-native:network:VirtualNetwork', vnet_name,
            virtual_network_name=vnet_name,
            resource_group_name=self.resource_group.name,
            location=location,
            address_space={'address_prefixes': ['10.0.0.0/16']},
            tags=tags,
        )

        # 3. Subnet
        subnet_name = self._cfg('subnet_name') or f'snet-{project}-{env}'
        self.subnet = factory.create('azure-native:network:Subnet', subnet_name,
            subnet_name=subnet_name,
            resource_group_name=self.resource_group.name,
            virtual_network_name=self.vnet.name,
            address_prefix='10.0.1.0/24',
        )

        # 4. NSG with SSH access
        nsg_name = self._cfg('nsg_name') or f'nsg-{project}-{env}'
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
            pip_name = self._cfg('pip_name') or f'pip-{project}-{env}'
            self.public_ip = factory.create('azure-native:network:PublicIPAddress', pip_name,
                public_ip_address_name=pip_name,
                resource_group_name=self.resource_group.name,
                location=location,
                sku={'name': 'Standard'},
                public_ip_allocation_method='Static',
                tags=tags,
            )

        # 6. Network Interface
        nic_name = self._cfg('nic_name') or f'nic-{project}-{env}'
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
        vm_name = self._cfg('vm_name') or f'vm-{project}-{env}'
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
        pulumi.export('environment', env)
        if enable_pip:
            pulumi.export('pip_name', pip_name)
            pulumi.export('public_ip', self.public_ip.ip_address)
            pulumi.export('ssh_command', self.public_ip.ip_address.apply(
                lambda ip: f'ssh {admin_username}@{ip}' if ip else 'N/A (no public IP)'
            ))

        return self.get_outputs()

    def get_outputs(self) -> Dict[str, Any]:
        return {
            'resource_group_name': self.resource_group.name if self.resource_group else None,
            'vm_id': self.vm.id if self.vm else None,
            'vm_name': self.vm.name if self.vm else None,
            'vnet_id': self.vnet.id if self.vnet else None,
            'subnet_id': self.subnet.id if self.subnet else None,
            'nsg_id': self.nsg.id if self.nsg else None,
            'nic_id': self.nic.id if self.nic else None,
            'public_ip': self.public_ip.ip_address if self.public_ip else None,
        }

    @classmethod
    def get_metadata(cls) -> Dict[str, Any]:
        return {
            'name': 'azure-vm-nonprod',
            'title': 'Virtual Machine',
            'description': 'Cost-optimized Azure VM with VNet, NSG, managed identity, and optional public IP. For dev/staging workloads.',
            'category': 'compute',
            'version': '1.0.0',
            'author': 'Archie',
            'cloud': 'azure',
            'environment': 'nonprod',
            'base_cost': '$35-60/month',
            'deployment_time': '5-8 minutes',
            'complexity': 'beginner',
            'features': [
                'Ubuntu 22.04 LTS with configurable VM size',
                'VNet with NSG and SSH access control',
                'Managed identity for Azure RBAC',
                'Optional public IP with static allocation',
                'Managed OS disk with configurable size',
                'Standard tagging and naming',
            ],
            'tags': ['azure', 'compute', 'vm', 'nonprod'],
            'use_cases': [
                'Development workstations',
                'CI/CD build agents',
                'Testing environments',
                'Small application servers',
            ],
            'pillars': [
                {
                    'title': 'Security',
                    'score': 'good',
                    'score_color': '#10b981',
                    'description': 'NSG restricts SSH access, managed identity for RBAC',
                    'practices': [
                        'NSG with configurable SSH source IP restriction',
                        'System-assigned managed identity',
                        'SSH key authentication supported',
                        'No open ports beyond SSH',
                    ],
                },
                {
                    'title': 'Operational Excellence',
                    'score': 'good',
                    'score_color': '#10b981',
                    'description': 'Standard naming, tagging, and managed identity',
                    'practices': [
                        'Consistent resource naming convention',
                        'Standard tagging for cost tracking',
                        'Managed identity eliminates credential management',
                    ],
                },
                {
                    'title': 'Cost Optimization',
                    'score': 'excellent',
                    'score_color': '#10b981',
                    'description': 'Cost-optimized VM size and Standard_LRS disk for non-prod',
                    'practices': [
                        'Configurable VM size for right-sizing',
                        'Standard_LRS disk (no premium for non-prod)',
                        'Optional public IP to reduce cost',
                    ],
                },
                {
                    'title': 'Reliability',
                    'score': 'needs-improvement',
                    'score_color': '#f59e0b',
                    'description': 'Single VM, no redundancy (appropriate for non-prod)',
                    'practices': [
                        'Single VM — no availability set or zone',
                        'Managed disk with Azure-managed replication',
                        'Non-prod: availability not critical',
                    ],
                },
                {
                    'title': 'Sustainability',
                    'score': 'good',
                    'score_color': '#10b981',
                    'description': 'Right-sized for non-prod, no over-provisioning',
                    'practices': [
                        'Configurable VM size avoids waste',
                        'Standard_LRS uses less redundant storage',
                        'Optional public IP reduces unused resources',
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
                    'default': 'centralus',
                    'title': 'Azure Region',
                    'description': 'Azure region for all resources',
                    'order': 3,
                    'group': 'Essentials',
                    'isEssential': True,
                },
                'vm_size': {
                    'type': 'string',
                    'default': 'Standard_D2s_v3',
                    'title': 'VM Size',
                    'description': 'Azure VM size',
                    'enum': ['Standard_B1s', 'Standard_B2s', 'Standard_D2s_v3', 'Standard_D4s_v3'],
                    'order': 10,
                    'group': 'Compute',
                    'cost_impact': '$15-120/month',
                },
                'disk_size_gb': {
                    'type': 'number',
                    'default': 30,
                    'title': 'OS Disk Size (GB)',
                    'description': 'Size of the managed OS disk',
                    'minimum': 30,
                    'maximum': 1024,
                    'order': 11,
                    'group': 'Compute',
                },
                'admin_username': {
                    'type': 'string',
                    'default': 'azureuser',
                    'title': 'Admin Username',
                    'description': 'SSH login username',
                    'order': 20,
                    'group': 'Security & Access',
                },
                'ssh_public_key': {
                    'type': 'string',
                    'default': '',
                    'title': 'SSH Public Key',
                    'description': 'SSH public key for key-based authentication',
                    'format': 'textarea',
                    'order': 21,
                    'group': 'Security & Access',
                },
                'ssh_access_ip': {
                    'type': 'string',
                    'default': '*',
                    'title': 'SSH Source IP',
                    'description': 'Source IP CIDR for SSH access (use * for any)',
                    'order': 22,
                    'group': 'Security & Access',
                },
                'enable_public_ip': {
                    'type': 'boolean',
                    'default': True,
                    'title': 'Enable Public IP',
                    'description': 'Assign a static public IP to the VM',
                    'order': 23,
                    'group': 'Security & Access',
                    'cost_impact': '+$3/month',
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
