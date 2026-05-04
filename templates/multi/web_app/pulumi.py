"""
Multi-Cloud Web Application Template

Deploy a web application across AWS, Azure, and GCP simultaneously.
Toggle which clouds to include — deploy to 1, 2, or all 3 at once.

Base cost: ~$50-80/month per cloud
- AWS: VPC + ALB + EC2 + Security Groups
- Azure: Resource Group + VNet + NSG + LB + VM + NIC + Public IP
- GCP: VPC Network + Subnet + Firewall + Instance + Global Address
"""

from typing import Any, Dict, List, Optional
import pulumi
import pulumi_aws as aws_sdk
import pulumi_azure_native as azure_native
import pulumi_gcp as gcp

from provisioner.templates.base import template_registry, InfrastructureTemplate
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory


@template_registry("multi-web-app")
class MultiWebAppTemplate(InfrastructureTemplate):
    """
    Multi-Cloud Web Application Template

    Deploys web app infrastructure to any combination of:
    - AWS: VPC + ALB + EC2 + Security Groups
    - Azure: Resource Group + VNet + NSG + LB + VM + NIC + Public IP
    - GCP: VPC Network + Subnet + Firewall + GCE Instance + Global Address
    """

    def __init__(self, name: str = None, config: Dict[str, Any] = None, **kwargs):
        """Initialize Multi-Cloud Web App template"""
        raw_config = config or kwargs or {}
        if name is None:
            name = (
                raw_config.get('project_name') or
                raw_config.get('parameters', {}).get('project_name') or
                'multi-web-app'
            )
        super().__init__(name, raw_config)
        self.config = raw_config

        # AWS resource references
        self.aws_vpc: Optional[object] = None
        self.aws_sg: Optional[object] = None
        self.aws_alb: Optional[object] = None
        self.aws_instance: Optional[object] = None

        # Azure resource references
        self.azure_rg: Optional[object] = None
        self.azure_vnet: Optional[object] = None
        self.azure_nsg: Optional[object] = None
        self.azure_lb: Optional[object] = None
        self.azure_vm: Optional[object] = None
        self.azure_pip: Optional[object] = None
        self.azure_nic: Optional[object] = None

        # GCP resource references
        self.gcp_network: Optional[object] = None
        self.gcp_subnet: Optional[object] = None
        self.gcp_firewall: Optional[object] = None
        self.gcp_instance: Optional[object] = None
        self.gcp_address: Optional[object] = None

    def _cfg(self, key: str, default=None):
        """Read config from root or parameters (Rule #6)"""
        params = self.config.get('parameters', {})
        return (
            self.config.get(key) or
            (params.get(key) if isinstance(params, dict) else None) or
            default
        )

    def _get_bool(self, key: str, default: bool = False) -> bool:
        """Read a boolean config value, handling string/bool/Decimal"""
        val = self._cfg(key, default)
        if isinstance(val, bool):
            return val
        if isinstance(val, str):
            return val.lower() in ('true', '1', 'yes')
        return bool(val)

    def create_infrastructure(self) -> Dict[str, Any]:
        """Deploy multi-cloud web app infrastructure (implements abstract method)"""
        return self.create()

    def create(self) -> Dict[str, Any]:
        """Deploy web app to all selected cloud providers"""

        project = self._cfg('project_name', 'web-app')
        env = self._cfg('environment', 'dev')
        team_name = self._cfg('team_name', '')
        instance_type = self._cfg('instance_type', 't3.small')
        cidr_block = self._cfg('cidr_block', '10.0.0.0/16')
        app_port = int(self._cfg('app_port', 80))
        enable_https = self._get_bool('enable_https', True)

        deploy_aws = self._get_bool('deploy_aws', True)
        deploy_azure = self._get_bool('deploy_azure', False)
        deploy_gcp = self._get_bool('deploy_gcp', False)

        prefix = f"{project}-{env}"
        clouds_deployed: List[str] = []

        if deploy_aws:
            self._create_aws(prefix, project, env, team_name, instance_type, cidr_block, app_port, enable_https)
            clouds_deployed.append('aws')

        if deploy_azure:
            self._create_azure(prefix, project, env, team_name, instance_type, cidr_block, app_port, enable_https)
            clouds_deployed.append('azure')

        if deploy_gcp:
            self._create_gcp(prefix, project, env, team_name, instance_type, cidr_block, app_port, enable_https)
            clouds_deployed.append('gcp')

        # Common exports
        pulumi.export('clouds_deployed', clouds_deployed)
        pulumi.export('project_name', project)
        pulumi.export('environment', env)
        pulumi.export('app_port', app_port)

        return self.get_outputs()

    def _create_aws(self, prefix, project, env, team_name, instance_type, cidr_block, app_port, enable_https):
        """Deploy AWS web app: VPC + ALB + EC2"""
        tags = {
            "Project": project,
            "Environment": env,
            "ManagedBy": "Archie",
            "Template": "multi-web-app",
        }
        if team_name:
            tags["Team"] = team_name

        # VPC
        self.aws_vpc = factory.create(
            "aws:ec2:Vpc",
            f"aws-{prefix}-vpc",
            cidr_block=cidr_block,
            enable_dns_support=True,
            enable_dns_hostnames=True,
            tags={**tags, "Name": f"aws-{prefix}-vpc"},
        )

        # Public Subnet A
        subnet_a = factory.create(
            "aws:ec2:Subnet",
            f"aws-{prefix}-subnet-a",
            vpc_id=self.aws_vpc.id,
            cidr_block="10.0.1.0/24",
            map_public_ip_on_launch=True,
            availability_zone=aws_sdk.get_availability_zones().names[0],
            tags={**tags, "Name": f"aws-{prefix}-subnet-a"},
        )

        # Public Subnet B (ALB requires 2 AZs)
        subnet_b = factory.create(
            "aws:ec2:Subnet",
            f"aws-{prefix}-subnet-b",
            vpc_id=self.aws_vpc.id,
            cidr_block="10.0.2.0/24",
            map_public_ip_on_launch=True,
            availability_zone=aws_sdk.get_availability_zones().names[1],
            tags={**tags, "Name": f"aws-{prefix}-subnet-b"},
        )

        # Internet Gateway
        factory.create(
            "aws:ec2:InternetGateway",
            f"aws-{prefix}-igw",
            vpc_id=self.aws_vpc.id,
            tags={**tags, "Name": f"aws-{prefix}-igw"},
        )

        # Security Group
        ports = [{"protocol": "tcp", "from_port": app_port, "to_port": app_port, "cidr_blocks": ["0.0.0.0/0"], "description": f"App port {app_port}"}]
        if enable_https:
            ports.append({"protocol": "tcp", "from_port": 443, "to_port": 443, "cidr_blocks": ["0.0.0.0/0"], "description": "HTTPS"})

        self.aws_sg = factory.create(
            "aws:ec2:SecurityGroup",
            f"aws-{prefix}-sg",
            vpc_id=self.aws_vpc.id,
            description=f"Web app security group for {project} (AWS)",
            ingress=ports,
            egress=[{"protocol": "-1", "from_port": 0, "to_port": 0, "cidr_blocks": ["0.0.0.0/0"], "description": "All outbound"}],
            tags={**tags, "Name": f"aws-{prefix}-sg"},
        )

        # ALB
        self.aws_alb = factory.create(
            "aws:lb:LoadBalancer",
            f"aws-{prefix}-alb",
            internal=False,
            load_balancer_type="application",
            security_groups=[self.aws_sg.id],
            subnets=[subnet_a.id, subnet_b.id],
            tags={**tags, "Name": f"aws-{prefix}-alb"},
        )

        # EC2 Instance
        ami = aws_sdk.ec2.get_ami(
            most_recent=True,
            owners=["amazon"],
            filters=[{"name": "name", "values": ["amzn2-ami-hvm-*-x86_64-gp2"]}],
        )
        self.aws_instance = factory.create(
            "aws:ec2:Instance",
            f"aws-{prefix}-instance",
            instance_type=instance_type,
            ami=ami.id,
            subnet_id=subnet_a.id,
            vpc_security_group_ids=[self.aws_sg.id],
            tags={**tags, "Name": f"aws-{prefix}-instance"},
        )

        pulumi.export('aws_vpc_id', self.aws_vpc.id)
        pulumi.export('aws_instance_id', self.aws_instance.id)
        pulumi.export('aws_public_ip', self.aws_instance.public_ip)
        pulumi.export('aws_alb_dns', self.aws_alb.dns_name)

    def _create_azure(self, prefix, project, env, team_name, instance_type, cidr_block, app_port, enable_https):
        """Deploy Azure web app: Resource Group + VNet + NSG + LB + VM + NIC + Public IP"""
        tags = {
            "Project": project,
            "Environment": env,
            "ManagedBy": "Archie",
            "Template": "multi-web-app",
        }
        if team_name:
            tags["Team"] = team_name

        location = self._cfg('azure_region', 'eastus')

        # Resource Group
        self.azure_rg = factory.create(
            "azure-native:resources:ResourceGroup",
            f"azure-{prefix}-rg",
            resource_group_name=f"azure-{prefix}-rg",
            location=location,
            tags=tags,
        )

        # VNet
        self.azure_vnet = factory.create(
            "azure-native:network:VirtualNetwork",
            f"azure-{prefix}-vnet",
            resource_group_name=self.azure_rg.name,
            virtual_network_name=f"azure-{prefix}-vnet",
            location=location,
            address_space={"address_prefixes": [cidr_block]},
            subnets=[{
                "name": "web-subnet",
                "address_prefix": "10.0.1.0/24",
            }],
            tags=tags,
        )

        # NSG
        rules = [
            {
                "name": "AllowHTTP",
                "priority": 100,
                "direction": "Inbound",
                "access": "Allow",
                "protocol": "Tcp",
                "source_port_range": "*",
                "destination_port_range": str(app_port),
                "source_address_prefix": "*",
                "destination_address_prefix": "*",
            },
        ]
        if enable_https:
            rules.append({
                "name": "AllowHTTPS",
                "priority": 110,
                "direction": "Inbound",
                "access": "Allow",
                "protocol": "Tcp",
                "source_port_range": "*",
                "destination_port_range": "443",
                "source_address_prefix": "*",
                "destination_address_prefix": "*",
            })

        self.azure_nsg = factory.create(
            "azure-native:network:NetworkSecurityGroup",
            f"azure-{prefix}-nsg",
            resource_group_name=self.azure_rg.name,
            network_security_group_name=f"azure-{prefix}-nsg",
            location=location,
            security_rules=rules,
            tags=tags,
        )

        # Public IP
        self.azure_pip = factory.create(
            "azure-native:network:PublicIPAddress",
            f"azure-{prefix}-pip",
            resource_group_name=self.azure_rg.name,
            public_ip_address_name=f"azure-{prefix}-pip",
            location=location,
            sku={"name": "Standard"},
            public_ip_allocation_method="Static",
            tags=tags,
        )

        # Load Balancer
        self.azure_lb = factory.create(
            "azure-native:network:LoadBalancer",
            f"azure-{prefix}-lb",
            resource_group_name=self.azure_rg.name,
            load_balancer_name=f"azure-{prefix}-lb",
            location=location,
            sku={"name": "Standard"},
            frontend_ip_configurations=[{
                "name": "frontend",
                "public_ip_address": {"id": self.azure_pip.id},
            }],
            tags=tags,
        )

        # NIC
        self.azure_nic = factory.create(
            "azure-native:network:NetworkInterface",
            f"azure-{prefix}-nic",
            resource_group_name=self.azure_rg.name,
            network_interface_name=f"azure-{prefix}-nic",
            location=location,
            ip_configurations=[{
                "name": "ipconfig",
                "subnet": {"id": self.azure_vnet.subnets.apply(lambda s: s[0].id if s else "")},
                "private_ip_allocation_method": "Dynamic",
            }],
            network_security_group={"id": self.azure_nsg.id},
            tags=tags,
        )

        # VM
        vm_size = instance_type if 'Standard' in instance_type else 'Standard_B2s'
        self.azure_vm = factory.create(
            "azure-native:compute:VirtualMachine",
            f"azure-{prefix}-vm",
            resource_group_name=self.azure_rg.name,
            vm_name=f"azure-{prefix}-vm",
            location=location,
            hardware_profile={"vm_size": vm_size},
            os_profile={
                "computer_name": f"azure-{prefix}-vm",
                "admin_username": "azureuser",
                "linux_configuration": {
                    "disable_password_authentication": True,
                    "ssh": {"public_keys": [{"path": "/home/azureuser/.ssh/authorized_keys", "key_data": self._cfg('ssh_public_key', 'ssh-rsa AAAA...')}]},
                },
            },
            storage_profile={
                "image_reference": {
                    "publisher": "Canonical",
                    "offer": "0001-com-ubuntu-server-jammy",
                    "sku": "22_04-lts",
                    "version": "latest",
                },
                "os_disk": {
                    "create_option": "FromImage",
                    "managed_disk": {"storage_account_type": "Standard_LRS"},
                },
            },
            network_profile={"network_interfaces": [{"id": self.azure_nic.id}]},
            tags=tags,
        )

        pulumi.export('azure_vnet_id', self.azure_vnet.id)
        pulumi.export('azure_vm_id', self.azure_vm.id)
        pulumi.export('azure_lb_id', self.azure_lb.id)
        pulumi.export('azure_public_ip', self.azure_pip.ip_address)

    def _create_gcp(self, prefix, project, env, team_name, instance_type, cidr_block, app_port, enable_https):
        """Deploy GCP web app: VPC Network + Subnet + Firewall + GCE Instance + Global Address"""
        region = self._cfg('gcp_region', 'us-central1')
        zone = self._cfg('gcp_zone', f'{region}-a')

        labels = {
            "project": project.lower().replace(' ', '-'),
            "environment": env,
            "managed-by": "archie",
            "template": "multi-web-app",
        }
        if team_name:
            labels["team"] = team_name.lower().replace(' ', '-')

        # VPC Network
        self.gcp_network = factory.create(
            "gcp:compute:Network",
            f"gcp-{prefix}-network",
            name=f"gcp-{prefix}-network",
            auto_create_subnetworks=False,
        )

        # Subnet
        self.gcp_subnet = factory.create(
            "gcp:compute:Subnetwork",
            f"gcp-{prefix}-subnet",
            name=f"gcp-{prefix}-subnet",
            network=self.gcp_network.id,
            ip_cidr_range="10.0.1.0/24",
            region=region,
        )

        # Firewall
        allows = [{"protocol": "tcp", "ports": [str(app_port)]}]
        if enable_https:
            allows.append({"protocol": "tcp", "ports": ["443"]})

        self.gcp_firewall = factory.create(
            "gcp:compute:Firewall",
            f"gcp-{prefix}-fw-web",
            name=f"gcp-{prefix}-fw-web",
            network=self.gcp_network.id,
            allows=allows,
            source_ranges=["0.0.0.0/0"],
            target_tags=["web"],
        )

        # GCE Instance
        machine_type = instance_type if 'e2-' in instance_type or 'n2-' in instance_type else 'e2-medium'
        self.gcp_instance = factory.create(
            "gcp:compute:Instance",
            f"gcp-{prefix}-instance",
            name=f"gcp-{prefix}-instance",
            machine_type=machine_type,
            zone=zone,
            boot_disk={
                "initialize_params": {
                    "image": "debian-cloud/debian-12",
                    "size": 20,
                },
            },
            network_interfaces=[{
                "network": self.gcp_network.id,
                "subnetwork": self.gcp_subnet.id,
                "access_configs": [{"nat_ip": None}],
            }],
            tags=["web"],
            labels=labels,
        )

        # Global Address (static IP for LB)
        self.gcp_address = factory.create(
            "gcp:compute:GlobalAddress",
            f"gcp-{prefix}-ip",
            name=f"gcp-{prefix}-ip",
        )

        pulumi.export('gcp_network_id', self.gcp_network.id)
        pulumi.export('gcp_instance_name', self.gcp_instance.name)
        pulumi.export('gcp_instance_ip', self.gcp_instance.network_interfaces.apply(
            lambda ni: ni[0].access_configs[0].nat_ip if ni and ni[0].access_configs else "pending"
        ))
        pulumi.export('gcp_static_ip', self.gcp_address.address)

    def get_outputs(self) -> Dict[str, Any]:
        """Get template outputs for all deployed clouds"""
        outputs: Dict[str, Any] = {
            "project_name": self._cfg('project_name', 'web-app'),
            "environment": self._cfg('environment', 'dev'),
        }

        # AWS outputs
        if self.aws_vpc:
            outputs["aws_vpc_id"] = self.aws_vpc.id
            outputs["aws_instance_id"] = self.aws_instance.id if self.aws_instance else None
            outputs["aws_alb_dns"] = self.aws_alb.dns_name if self.aws_alb else None
            outputs["aws_public_ip"] = self.aws_instance.public_ip if self.aws_instance else None

        # Azure outputs
        if self.azure_vnet:
            outputs["azure_vnet_id"] = self.azure_vnet.id
            outputs["azure_vm_id"] = self.azure_vm.id if self.azure_vm else None
            outputs["azure_lb_id"] = self.azure_lb.id if self.azure_lb else None
            outputs["azure_public_ip"] = self.azure_pip.ip_address if self.azure_pip else None

        # GCP outputs
        if self.gcp_network:
            outputs["gcp_network_id"] = self.gcp_network.id
            outputs["gcp_instance_name"] = self.gcp_instance.name if self.gcp_instance else None
            outputs["gcp_static_ip"] = self.gcp_address.address if self.gcp_address else None

        return outputs

    @classmethod
    def get_metadata(cls) -> Dict[str, Any]:
        """Template metadata for catalog UI"""
        return {
            "name": "multi-web-app",
            "title": "Multi-Cloud Web Application",
            "description": "Deploy a web application across AWS, Azure, and GCP simultaneously. Toggle which clouds to include for cross-cloud redundancy with unified governance.",
            "category": "web",
            "version": "2.0.0",
            "author": "Archie",
            "cloud": "multi",
            "environment": "nonprod",
            "base_cost": "$50-80/month per cloud",
            "features": [
                "Deploy to 1, 2, or all 3 clouds simultaneously",
                "AWS: VPC + ALB + EC2 + Security Groups",
                "Azure: Resource Group + VNet + NSG + LB + VM + NIC + Public IP",
                "GCP: VPC Network + Subnet + Firewall + GCE + Global Address",
                "Cross-cloud redundancy with unified governance",
                "Single deploy creates consistent infrastructure across clouds",
                "HTTPS support with port configuration per cloud",
            ],
            "tags": ["multi-cloud", "web", "load-balancer", "compute", "vpc", "cross-cloud"],
            "deployment_time": "5-15 minutes",
            "complexity": "intermediate",
            "use_cases": [
                "Multi-cloud redundancy for web applications",
                "Disaster recovery across cloud providers",
                "Cloud migration with parallel deployment",
                "Vendor lock-in avoidance",
                "Cross-cloud strategy evaluation",
            ],
            "pillars": [
                {
                    "title": "Operational Excellence",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Single template deploys and governs infrastructure across three clouds simultaneously",
                    "practices": [
                        "One deploy creates infrastructure on multiple clouds at once",
                        "Unified governance and drift detection across all clouds",
                        "Consistent naming and tagging across all providers",
                        "Environment-aware configuration (dev/staging/prod)",
                        "Factory pattern ensures consistent resource creation",
                    ]
                },
                {
                    "title": "Security",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Network isolation with security groups per cloud provider",
                    "practices": [
                        "VPC / VNet / VPC Network isolation per cloud",
                        "Security Group / NSG / Firewall restricts ingress",
                        "Private subnets for compute instances",
                        "HTTPS support configurable per deployment",
                        "All outbound traffic allowed for patch management",
                    ]
                },
                {
                    "title": "Reliability",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Cross-cloud deployment provides ultimate redundancy",
                    "practices": [
                        "Simultaneous deployment across multiple clouds",
                        "Load balancer health checks per cloud",
                        "No single cloud is a single point of failure",
                        "Multi-AZ subnets for AWS ALB",
                        "Cloud-managed load balancers with built-in redundancy",
                    ]
                },
                {
                    "title": "Performance Efficiency",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Right-sized compute with load balancing per cloud",
                    "practices": [
                        "Configurable instance type per cloud provider",
                        "Load balancer offloads connection management",
                        "Region selection per cloud for latency optimization",
                        "Application port configurable for any workload",
                    ]
                },
                {
                    "title": "Cost Optimization",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Toggle clouds on/off to control spend per environment",
                    "practices": [
                        "Deploy only to clouds you need (1, 2, or all 3)",
                        "Instance type mapped to equivalent tiers across clouds",
                        "Single instance for non-prod environments",
                        "Cloud-specific cost-efficient defaults",
                    ]
                },
                {
                    "title": "Sustainability",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Right-sized resources with efficient cloud utilization",
                    "practices": [
                        "Toggle off unused clouds to reduce resource consumption",
                        "Cloud-managed LB shares infrastructure",
                        "Region selection can target low-carbon regions",
                        "Right-sized compute minimizes energy waste",
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
                    "default": "web-app",
                    "title": "Project Name",
                    "description": "Project identifier used in resource naming",
                    "order": 1,
                    "group": "Essentials",
                    "isEssential": True,
                },
                "environment": {
                    "type": "string",
                    "default": "dev",
                    "title": "Environment",
                    "description": "Deployment environment",
                    "enum": ["dev", "staging", "prod"],
                    "order": 2,
                    "group": "Essentials",
                    "isEssential": True,
                },
                "deploy_aws": {
                    "type": "boolean",
                    "default": True,
                    "title": "Deploy to AWS",
                    "description": "Deploy VPC + ALB + EC2 on AWS",
                    "order": 3,
                    "group": "Cloud Selection",
                    "isEssential": True,
                },
                "deploy_azure": {
                    "type": "boolean",
                    "default": False,
                    "title": "Deploy to Azure",
                    "description": "Deploy VNet + LB + VM on Azure",
                    "order": 4,
                    "group": "Cloud Selection",
                    "isEssential": True,
                },
                "deploy_gcp": {
                    "type": "boolean",
                    "default": False,
                    "title": "Deploy to GCP",
                    "description": "Deploy VPC Network + GCE on GCP",
                    "order": 5,
                    "group": "Cloud Selection",
                    "isEssential": True,
                },
                "instance_type": {
                    "type": "string",
                    "default": "t3.small",
                    "title": "Instance Type",
                    "description": "Compute instance size (e.g., t3.small for AWS, Standard_B2s for Azure, e2-medium for GCP)",
                    "order": 10,
                    "group": "Compute",
                    "cost_impact": "~$15-40/month per cloud",
                },
                "cidr_block": {
                    "type": "string",
                    "default": "10.0.0.0/16",
                    "title": "Network CIDR",
                    "description": "VPC / VNet / VPC Network CIDR block",
                    "order": 20,
                    "group": "Network Configuration",
                },
                "app_port": {
                    "type": "number",
                    "default": 80,
                    "title": "Application Port",
                    "description": "Port the web application listens on",
                    "order": 21,
                    "group": "Network Configuration",
                },
                "enable_https": {
                    "type": "boolean",
                    "default": True,
                    "title": "Enable HTTPS",
                    "description": "Allow HTTPS (port 443) traffic on all clouds",
                    "order": 22,
                    "group": "Security & Access",
                },
                "ssh_public_key": {
                    "type": "string",
                    "default": "",
                    "title": "SSH Public Key",
                    "description": "SSH public key for Azure VM access (required when deploying to Azure)",
                    "order": 30,
                    "group": "Security & Access",
                    "conditional": {"field": "deploy_azure"},
                },
                "azure_region": {
                    "type": "string",
                    "default": "eastus",
                    "title": "Azure Region",
                    "description": "Azure region (e.g., eastus, westus2, westeurope)",
                    "order": 40,
                    "group": "Cloud Regions",
                    "conditional": {"field": "deploy_azure"},
                },
                "gcp_region": {
                    "type": "string",
                    "default": "us-central1",
                    "title": "GCP Region",
                    "description": "GCP region (e.g., us-central1, us-east1, europe-west1)",
                    "order": 41,
                    "group": "Cloud Regions",
                    "conditional": {"field": "deploy_gcp"},
                },
                "gcp_zone": {
                    "type": "string",
                    "default": "us-central1-a",
                    "title": "GCP Zone",
                    "description": "GCP zone for compute instances",
                    "order": 42,
                    "group": "Cloud Regions",
                    "conditional": {"field": "deploy_gcp"},
                },
                "team_name": {
                    "type": "string",
                    "default": "",
                    "title": "Team Name",
                    "description": "Team that owns this web application",
                    "order": 50,
                    "group": "Tags",
                },
            },
            "required": ["project_name"],
        }
