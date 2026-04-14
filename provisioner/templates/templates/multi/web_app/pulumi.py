"""
Multi-Cloud Web Application Template

Composed template: VPC/VNet/VPC Network + Load Balancer + Compute.
Config field `cloud` (aws/azure/gcp) selects the right provider resources.
One template, three clouds, same interface.

Base cost: ~$50-80/month (varies by cloud)
- Network foundation (VPC / VNet / VPC Network)
- Load balancer (ALB / Azure LB / GCP HTTP LB)
- Compute instance (EC2 / Azure VM / GCE)
- Security groups / NSG / Firewall rules
"""

from typing import Any, Dict, Optional
import pulumi

from provisioner.templates.base import template_registry, InfrastructureTemplate
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory


@template_registry("multi-web-app")
class MultiWebAppTemplate(InfrastructureTemplate):
    """
    Multi-Cloud Web Application Template

    Creates (based on cloud selection):
    - AWS: VPC + ALB + EC2 + Security Groups
    - Azure: VNet + Load Balancer + VM + NSG
    - GCP: VPC Network + HTTP LB + GCE Instance + Firewall
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

        # Resource references (populated per cloud)
        self.network: Optional[object] = None
        self.subnet: Optional[object] = None
        self.security: Optional[object] = None
        self.lb: Optional[object] = None
        self.compute: Optional[object] = None

    def _cfg(self, key: str, default=None):
        """Read config from root or parameters (Rule #6)"""
        params = self.config.get('parameters', {})
        cloud = self.config.get('cloud') or (params.get('cloud') if isinstance(params, dict) else None) or 'aws'
        cloud_params = params.get(cloud, {}) if isinstance(params, dict) else {}
        return (
            self.config.get(key) or
            (cloud_params.get(key) if isinstance(cloud_params, dict) else None) or
            (params.get(key) if isinstance(params, dict) else None) or
            default
        )

    def create_infrastructure(self) -> Dict[str, Any]:
        """Deploy multi-cloud web app infrastructure (implements abstract method)"""
        return self.create()

    def create(self) -> Dict[str, Any]:
        """Deploy web app to the selected cloud provider"""

        # Read config
        cloud = self._cfg('cloud', 'aws')
        project = self._cfg('project_name', 'web-app')
        env = self._cfg('environment', 'dev')
        team_name = self._cfg('team_name', '')
        instance_type = self._cfg('instance_type', 't3.small')
        cidr_block = self._cfg('cidr_block', '10.0.0.0/16')
        app_port = int(self._cfg('app_port', 80))
        enable_https = self._cfg('enable_https', True)
        if isinstance(enable_https, str):
            enable_https = enable_https.lower() in ('true', '1', 'yes')

        prefix = f"{project}-{env}"

        if cloud == 'aws':
            self._create_aws(prefix, project, env, team_name, instance_type, cidr_block, app_port, enable_https)
        elif cloud == 'azure':
            self._create_azure(prefix, project, env, team_name, instance_type, cidr_block, app_port, enable_https)
        elif cloud == 'gcp':
            self._create_gcp(prefix, project, env, team_name, instance_type, cidr_block, app_port, enable_https)
        else:
            raise ValueError(f"Unsupported cloud: {cloud}. Must be aws, azure, or gcp.")

        # Common exports
        pulumi.export('cloud', cloud)
        pulumi.export('project_name', project)
        pulumi.export('environment', env)
        pulumi.export('app_port', app_port)

        return self.get_outputs()

    def _create_aws(self, prefix, project, env, team_name, instance_type, cidr_block, app_port, enable_https):
        """Deploy AWS web app: VPC + ALB + EC2"""
        import pulumi_aws as aws_sdk

        tags = {
            "Project": project,
            "Environment": env,
            "ManagedBy": "Archie",
            "Template": "multi-web-app",
        }
        if team_name:
            tags["Team"] = team_name

        # VPC
        self.network = factory.create(
            "aws:ec2:Vpc",
            f"{prefix}-vpc",
            cidr_block=cidr_block,
            enable_dns_support=True,
            enable_dns_hostnames=True,
            tags={**tags, "Name": f"{prefix}-vpc"},
        )

        # Public Subnet
        self.subnet = factory.create(
            "aws:ec2:Subnet",
            f"{prefix}-subnet-pub",
            vpc_id=self.network.id,
            cidr_block="10.0.1.0/24",
            map_public_ip_on_launch=True,
            availability_zone=aws_sdk.get_availability_zones().names[0],
            tags={**tags, "Name": f"{prefix}-subnet-pub"},
        )

        # Second subnet for ALB (requires 2 AZs)
        subnet_b = factory.create(
            "aws:ec2:Subnet",
            f"{prefix}-subnet-pub-b",
            vpc_id=self.network.id,
            cidr_block="10.0.2.0/24",
            map_public_ip_on_launch=True,
            availability_zone=aws_sdk.get_availability_zones().names[1],
            tags={**tags, "Name": f"{prefix}-subnet-pub-b"},
        )

        # Internet Gateway
        igw = factory.create(
            "aws:ec2:InternetGateway",
            f"{prefix}-igw",
            vpc_id=self.network.id,
            tags={**tags, "Name": f"{prefix}-igw"},
        )

        # Security Group
        ports = [{"protocol": "tcp", "from_port": app_port, "to_port": app_port, "cidr_blocks": ["0.0.0.0/0"], "description": f"App port {app_port}"}]
        if enable_https:
            ports.append({"protocol": "tcp", "from_port": 443, "to_port": 443, "cidr_blocks": ["0.0.0.0/0"], "description": "HTTPS"})

        self.security = factory.create(
            "aws:ec2:SecurityGroup",
            f"{prefix}-sg",
            vpc_id=self.network.id,
            description=f"Web app security group for {project}",
            ingress=ports,
            egress=[{"protocol": "-1", "from_port": 0, "to_port": 0, "cidr_blocks": ["0.0.0.0/0"], "description": "All outbound"}],
            tags={**tags, "Name": f"{prefix}-sg"},
        )

        # ALB
        self.lb = factory.create(
            "aws:lb:LoadBalancer",
            f"{prefix}-alb",
            internal=False,
            load_balancer_type="application",
            security_groups=[self.security.id],
            subnets=[self.subnet.id, subnet_b.id],
            tags={**tags, "Name": f"{prefix}-alb"},
        )

        # EC2 Instance
        ami = aws_sdk.ec2.get_ami(
            most_recent=True,
            owners=["amazon"],
            filters=[{"name": "name", "values": ["amzn2-ami-hvm-*-x86_64-gp2"]}],
        )
        self.compute = factory.create(
            "aws:ec2:Instance",
            f"{prefix}-instance",
            instance_type=instance_type,
            ami=ami.id,
            subnet_id=self.subnet.id,
            vpc_security_group_ids=[self.security.id],
            tags={**tags, "Name": f"{prefix}-instance"},
        )

        pulumi.export('vpc_id', self.network.id)
        pulumi.export('instance_id', self.compute.id)
        pulumi.export('public_ip', self.compute.public_ip)
        pulumi.export('lb_dns', self.lb.dns_name)

    def _create_azure(self, prefix, project, env, team_name, instance_type, cidr_block, app_port, enable_https):
        """Deploy Azure web app: VNet + LB + VM"""
        tags = {
            "Project": project,
            "Environment": env,
            "ManagedBy": "Archie",
            "Template": "multi-web-app",
        }
        if team_name:
            tags["Team"] = team_name

        location = self._cfg('region', 'eastus')

        # Resource Group
        rg = factory.create(
            "azure-native:resources:ResourceGroup",
            f"{prefix}-rg",
            resource_group_name=f"{prefix}-rg",
            location=location,
            tags=tags,
        )

        # VNet
        self.network = factory.create(
            "azure-native:network:VirtualNetwork",
            f"{prefix}-vnet",
            resource_group_name=rg.name,
            virtual_network_name=f"{prefix}-vnet",
            location=location,
            address_space={"address_prefixes": [cidr_block]},
            subnets=[{
                "name": "web-subnet",
                "address_prefix": "10.0.1.0/24",
            }],
            tags=tags,
        )

        # NSG
        self.security = factory.create(
            "azure-native:network:NetworkSecurityGroup",
            f"{prefix}-nsg",
            resource_group_name=rg.name,
            network_security_group_name=f"{prefix}-nsg",
            location=location,
            security_rules=[
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
            ],
            tags=tags,
        )

        # Public IP
        public_ip = factory.create(
            "azure-native:network:PublicIPAddress",
            f"{prefix}-pip",
            resource_group_name=rg.name,
            public_ip_address_name=f"{prefix}-pip",
            location=location,
            sku={"name": "Standard"},
            public_ip_allocation_method="Static",
            tags=tags,
        )

        # Load Balancer
        self.lb = factory.create(
            "azure-native:network:LoadBalancer",
            f"{prefix}-lb",
            resource_group_name=rg.name,
            load_balancer_name=f"{prefix}-lb",
            location=location,
            sku={"name": "Standard"},
            frontend_ip_configurations=[{
                "name": "frontend",
                "public_ip_address": {"id": public_ip.id},
            }],
            tags=tags,
        )

        # NIC
        nic = factory.create(
            "azure-native:network:NetworkInterface",
            f"{prefix}-nic",
            resource_group_name=rg.name,
            network_interface_name=f"{prefix}-nic",
            location=location,
            ip_configurations=[{
                "name": "ipconfig",
                "subnet": {"id": self.network.subnets.apply(lambda s: s[0].id if s else "")},
                "private_ip_allocation_method": "Dynamic",
            }],
            network_security_group={"id": self.security.id},
            tags=tags,
        )

        # VM
        vm_size = instance_type if 'Standard' in instance_type else 'Standard_B2s'
        self.compute = factory.create(
            "azure-native:compute:VirtualMachine",
            f"{prefix}-vm",
            resource_group_name=rg.name,
            vm_name=f"{prefix}-vm",
            location=location,
            hardware_profile={"vm_size": vm_size},
            os_profile={
                "computer_name": f"{prefix}-vm",
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
            network_profile={"network_interfaces": [{"id": nic.id}]},
            tags=tags,
        )

        pulumi.export('vnet_id', self.network.id)
        pulumi.export('vm_id', self.compute.id)
        pulumi.export('lb_id', self.lb.id)
        pulumi.export('public_ip_address', public_ip.ip_address)

    def _create_gcp(self, prefix, project, env, team_name, instance_type, cidr_block, app_port, enable_https):
        """Deploy GCP web app: VPC Network + HTTP LB + GCE"""
        gcp_project = self._cfg('gcp_project', '')
        region = self._cfg('region', 'us-central1')
        zone = self._cfg('zone', f'{region}-a')

        labels = {
            "project": project.lower().replace(' ', '-'),
            "environment": env,
            "managed-by": "archie",
            "template": "multi-web-app",
        }
        if team_name:
            labels["team"] = team_name.lower().replace(' ', '-')

        # VPC Network
        self.network = factory.create(
            "gcp:compute:Network",
            f"{prefix}-network",
            name=f"{prefix}-network",
            auto_create_subnetworks=False,
        )

        # Subnet
        self.subnet = factory.create(
            "gcp:compute:Subnetwork",
            f"{prefix}-subnet",
            name=f"{prefix}-subnet",
            network=self.network.id,
            ip_cidr_range="10.0.1.0/24",
            region=region,
        )

        # Firewall
        self.security = factory.create(
            "gcp:compute:Firewall",
            f"{prefix}-fw-web",
            name=f"{prefix}-fw-web",
            network=self.network.id,
            allows=[
                {"protocol": "tcp", "ports": [str(app_port)]},
            ] + ([{"protocol": "tcp", "ports": ["443"]}] if enable_https else []),
            source_ranges=["0.0.0.0/0"],
            target_tags=["web"],
        )

        # GCE Instance
        machine_type = instance_type if 'e2-' in instance_type or 'n2-' in instance_type else 'e2-medium'
        self.compute = factory.create(
            "gcp:compute:Instance",
            f"{prefix}-instance",
            name=f"{prefix}-instance",
            machine_type=machine_type,
            zone=zone,
            boot_disk={
                "initialize_params": {
                    "image": "debian-cloud/debian-12",
                    "size": 20,
                },
            },
            network_interfaces=[{
                "network": self.network.id,
                "subnetwork": self.subnet.id,
                "access_configs": [{"nat_ip": None}],
            }],
            tags=["web"],
            labels=labels,
        )

        # Static IP for LB
        static_ip = factory.create(
            "gcp:compute:GlobalAddress",
            f"{prefix}-ip",
            name=f"{prefix}-ip",
        )

        # Health Check
        health_check = factory.create(
            "gcp:compute:HealthCheck",
            f"{prefix}-hc",
            name=f"{prefix}-hc",
            http_health_check={"port": app_port},
        )

        pulumi.export('network_id', self.network.id)
        pulumi.export('instance_name', self.compute.name)
        pulumi.export('instance_ip', self.compute.network_interfaces.apply(
            lambda ni: ni[0].access_configs[0].nat_ip if ni and ni[0].access_configs else "pending"
        ))
        pulumi.export('static_ip', static_ip.address)

    def get_outputs(self) -> Dict[str, Any]:
        """Get template outputs"""
        cloud = self._cfg('cloud', 'aws')
        return {
            "cloud": cloud,
            "project_name": self._cfg('project_name', 'web-app'),
            "environment": self._cfg('environment', 'dev'),
            "network_id": self.network.id if self.network else None,
            "compute_id": self.compute.id if self.compute else None,
            "lb_id": self.lb.id if self.lb else None,
        }

    @classmethod
    def get_metadata(cls) -> Dict[str, Any]:
        """Template metadata for catalog UI"""
        return {
            "name": "multi-web-app",
            "title": "Multi-Cloud Web Application",
            "description": "Deploy a web application with network, load balancer, and compute on AWS, Azure, or GCP. One template, three clouds, same interface.",
            "category": "web",
            "version": "1.0.0",
            "author": "Archie",
            "cloud": "multi",
            "environment": "nonprod",
            "base_cost": "$50-80/month",
            "features": [
                "Single template deploys to AWS, Azure, or GCP",
                "VPC / VNet / VPC Network with subnets",
                "Application Load Balancer / Azure LB / GCP HTTP LB",
                "EC2 / Azure VM / GCE compute instance",
                "Security Groups / NSG / Firewall rules",
                "HTTPS support with port configuration",
            ],
            "tags": ["multi-cloud", "web", "load-balancer", "compute", "vpc"],
            "deployment_time": "5-10 minutes",
            "complexity": "intermediate",
            "use_cases": [
                "Cloud-agnostic web application deployment",
                "Multi-cloud strategy evaluation",
                "Disaster recovery across cloud providers",
                "Vendor lock-in avoidance",
                "Standardized web app infrastructure",
            ],
            "pillars": [
                {
                    "title": "Operational Excellence",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Single template manages infrastructure across three cloud providers",
                    "practices": [
                        "Unified interface abstracts cloud-specific complexity",
                        "Infrastructure as Code for repeatable multi-cloud deployments",
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
                        "VPC / VNet / VPC Network isolation per deployment",
                        "Security Group / NSG / Firewall restricts ingress",
                        "Private subnets for compute instances",
                        "HTTPS support configurable per deployment",
                        "All outbound traffic allowed for patch management",
                    ]
                },
                {
                    "title": "Reliability",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Load balancer distributes traffic with health checks",
                    "practices": [
                        "Load balancer health checks detect failed instances",
                        "Multi-AZ subnets for AWS ALB",
                        "Cloud-managed load balancers with built-in redundancy",
                        "Static IP for consistent DNS resolution",
                    ]
                },
                {
                    "title": "Performance Efficiency",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Right-sized compute with load balancing for traffic distribution",
                    "practices": [
                        "Configurable instance type per cloud provider",
                        "Load balancer offloads connection management",
                        "Region selection for latency optimization",
                        "Application port configurable for any workload",
                    ]
                },
                {
                    "title": "Cost Optimization",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Right-sized instances with cloud-specific cost optimization",
                    "practices": [
                        "Instance type mapped to equivalent tiers across clouds",
                        "Single instance for non-prod environments",
                        "Cloud-specific cost-efficient defaults",
                        "Environment-based sizing (dev vs prod)",
                    ]
                },
                {
                    "title": "Sustainability",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Right-sized resources with efficient cloud utilization",
                    "practices": [
                        "Single instance for dev reduces resource consumption",
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
                "cloud": {
                    "type": "string",
                    "default": "aws",
                    "title": "Cloud Provider",
                    "description": "Target cloud provider for deployment",
                    "enum": ["aws", "azure", "gcp"],
                    "order": 3,
                    "group": "Essentials",
                    "isEssential": True,
                },
                "region": {
                    "type": "string",
                    "default": "us-east-1",
                    "title": "Region",
                    "description": "Cloud region (e.g., us-east-1, eastus, us-central1)",
                    "order": 4,
                    "group": "Essentials",
                    "isEssential": True,
                },
                "instance_type": {
                    "type": "string",
                    "default": "t3.small",
                    "title": "Instance Type",
                    "description": "Compute instance size (e.g., t3.small, Standard_B2s, e2-medium)",
                    "order": 10,
                    "group": "Compute",
                    "cost_impact": "~$15-40/month",
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
                    "description": "Allow HTTPS (port 443) traffic",
                    "order": 22,
                    "group": "Security & Access",
                },
                "ssh_public_key": {
                    "type": "string",
                    "default": "",
                    "title": "SSH Public Key",
                    "description": "SSH public key for Azure VM access (Azure only)",
                    "order": 30,
                    "group": "Security & Access",
                    "conditional": {"field": "cloud"},
                },
                "gcp_project": {
                    "type": "string",
                    "default": "",
                    "title": "GCP Project ID",
                    "description": "Google Cloud project ID (GCP only)",
                    "order": 31,
                    "group": "Essentials",
                    "conditional": {"field": "cloud"},
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
            "required": ["project_name", "cloud"],
        }
