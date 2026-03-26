import pulumi
import pulumi_aws as aws
from provisioner.templates.base import InfrastructureTemplate, template_registry
from provisioner.utils.aws import ResourceNamer, get_standard_tags
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory

@template_registry("vpc-network")
class VPCNetworkTemplate(InfrastructureTemplate):
    def __init__(self, name=None, config=None, **kwargs):
        raw_config = config or kwargs or {}
        if name is None:
            name = raw_config.get('project_name', 'my-template')
        super().__init__(name, raw_config)

    def create_infrastructure(self):
        namer = ResourceNamer(
            project=self.config.get('project_name', 'proj'),
            environment=self.config.get('environment', 'prod'),
            region=self.config.get('region', 'us-east-1'),
            template='vpc-network'
        )

        # Create VPC
        vpc = factory.create('aws:ec2:Vpc', namer.name('main-vpc'), 
            cidr_block=self.config.get('vpc_cidr', '10.111.0.0/16'),
            enable_dns_support=True,
            enable_dns_hostnames=True,
            tags=get_standard_tags(Name='production-vpc', Environment='prod')
        )

        # Create Public Subnet
        public_subnet = factory.create('aws:ec2:Subnet', namer.name('public-subnet'),
            vpc_id=vpc.id,
            cidr_block=self.config.get('public_subnet_cidr', '10.111.1.0/24'),
            availability_zone=self.config.get('availability_zone', 'us-east-1a'),
            map_public_ip_on_launch=True,
            tags=get_standard_tags(Name='public-subnet', Tier='public')
        )

        # Create Private Subnet
        private_subnet = factory.create('aws:ec2:Subnet', namer.name('private-subnet'),
            vpc_id=vpc.id,
            cidr_block=self.config.get('private_subnet_cidr', '10.111.2.0/24'),
            availability_zone=self.config.get('availability_zone', 'us-east-1a'),
            tags=get_standard_tags(Name='private-subnet', Tier='private')
        )

        # Create Security Group
        web_sg = factory.create('aws:ec2:SecurityGroup', namer.name('web-sg'),
            vpc_id=vpc.id,
            description='Web tier - HTTP/HTTPS from internet',
            tags=get_standard_tags(Name='web-sg')
        )

        # Add security group rules
        http_rule = aws.ec2.SecurityGroupRule('http-ingress',
            type='ingress',
            from_port=80,
            to_port=80,
            protocol='tcp',
            cidr_blocks=['0.0.0.0/0'],
            security_group_id=web_sg.id
        )

        https_rule = aws.ec2.SecurityGroupRule('https-ingress',
            type='ingress',
            from_port=443,
            to_port=443,
            protocol='tcp',
            cidr_blocks=['0.0.0.0/0'],
            security_group_id=web_sg.id
        )

        egress_rule = aws.ec2.SecurityGroupRule('egress',
            type='egress',
            from_port=0,
            to_port=0,
            protocol='-1',
            cidr_blocks=['0.0.0.0/0'],
            security_group_id=web_sg.id
        )

        # Create Internet Gateway
        igw = factory.create('aws:ec2:InternetGateway', namer.name('main-igw'),
            vpc_id=vpc.id,
            tags=get_standard_tags(Name='main-igw')
        )

        # Create Route Table
        route_table = factory.create('aws:ec2:RouteTable', namer.name('public-rt'),
            vpc_id=vpc.id,
            routes=[{
                'cidr_block': '0.0.0.0/0',
                'gateway_id': igw.id
            }],
            tags=get_standard_tags(Name='public-rt')
        )

        # Route Table Association
        route_table_assoc = aws.ec2.RouteTableAssociation(namer.name('public-rt-assoc'),
            subnet_id=public_subnet.id,
            route_table_id=route_table.id
        )

        return self.get_outputs()

    def get_outputs(self):
        outputs = {
            'vpc_id': pulumi.get_resource_property('aws:ec2/vpc:Vpc', 'main-vpc', 'id'),
            'public_subnet_id': pulumi.get_resource_property('aws:ec2/subnet:Subnet', 'public-subnet', 'id'),
            'private_subnet_id': pulumi.get_resource_property('aws:ec2/subnet:Subnet', 'private-subnet', 'id'),
            'web_security_group_id': pulumi.get_resource_property('aws:ec2/securityGroup:SecurityGroup', 'web-sg', 'id')
        }
        
        for key, value in outputs.items():
            pulumi.export(key, value)
        
        return outputs

    @classmethod
    def get_metadata(cls):
        return {
            'name': 'vpc-network',
            'title': 'VPC with Public and Private Subnets',
            'description': 'Creates a VPC with a public and private subnet, internet gateway, and web security group',
            'category': 'networking',
            'cloud': 'aws',
            'tier': 'standard',
            'estimated_cost': '$10-20/mo',
            'deployment_time': '~10 min',
            'features': ['dns_support', 'public_subnet', 'private_subnet', 'internet_gateway'],
            'use_cases': ['web_hosting', 'microservices', 'application_infrastructure'],
            'pillars': ['reliability', 'performance', 'security'],
            'resources': [
                {'name': 'VPC', 'type': 'aws:ec2/vpc:Vpc', 'category': 'network', 'description': 'Virtual Private Cloud'},
                {'name': 'Public Subnet', 'type': 'aws:ec2/subnet:Subnet', 'category': 'network', 'description': 'Public-facing subnet'},
                {'name': 'Private Subnet', 'type': 'aws:ec2/subnet:Subnet', 'category': 'network', 'description': 'Private subnet for internal resources'},
                {'name': 'Internet Gateway', 'type': 'aws:ec2/internetGateway:InternetGateway', 'category': 'network', 'description': 'Internet gateway for VPC'}
            ],
            'config_fields': [
                {'name': 'vpc_cidr', 'type': 'text', 'label': 'VPC CIDR', 'required': True, 'default': '10.111.0.0/16', 'group': 'Network', 'helpText': 'CIDR block for the VPC'},
                {'name': 'public_subnet_cidr', 'type': 'text', 'label': 'Public Subnet CIDR', 'required': True, 'default': '10.111.1.0/24', 'group': 'Network', 'helpText': 'CIDR block for the public subnet'},
                {'name': 'private_subnet_cidr', 'type': 'text', 'label': 'Private Subnet CIDR', 'required': True, 'default': '10.111.2.0/24', 'group': 'Network', 'helpText': 'CIDR block for the private subnet'},
                {'name': 'availability_zone', 'type': 'select', 'label': 'Availability Zone', 'required': True, 'default': 'us-east-1a', 'group': 'Network', 'helpText': 'Availability zone for subnets', 'options': ['us-east-1a', 'us-east-1b', 'us-east-1c']}
            ]
        }
