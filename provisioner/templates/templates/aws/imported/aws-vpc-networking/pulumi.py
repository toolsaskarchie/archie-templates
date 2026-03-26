import pulumi
import pulumi_aws as aws
from provisioner.templates.base import InfrastructureTemplate, template_registry
from provisioner.utils.aws import ResourceNamer, get_standard_tags
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory

@template_registry("aws-vpc-networking")
class VPCNetworkTemplate(InfrastructureTemplate):
    @classmethod
    def get_metadata(cls):
        return {
            'name': 'aws-vpc-networking',
            'title': 'AWS Basic VPC Network',
            'description': 'Creates a basic VPC with public and private subnets',
            'category': 'networking',
            'cloud': 'aws',
            'tier': 'standard',
            'estimated_cost': '$5-10/mo',
            'deployment_time': '~5 min',
            'features': ['VPC', 'Public Subnet', 'Private Subnet', 'Internet Gateway', 'Route Table'],
            'use_cases': ['Web Applications', 'Network Isolation', 'Cloud Infrastructure'],
            'pillars': ['Security', 'Network'],
            'resources': [
                {'name': 'MainVPC', 'type': 'aws:ec2:Vpc', 'category': 'networking', 'description': 'Main VPC for the infrastructure'},
                {'name': 'PublicSubnet', 'type': 'aws:ec2:Subnet', 'category': 'networking', 'description': 'Public subnet in the VPC'},
                {'name': 'PrivateSubnet', 'type': 'aws:ec2:Subnet', 'category': 'networking', 'description': 'Private subnet in the VPC'},
                {'name': 'WebSecurityGroup', 'type': 'aws:ec2:SecurityGroup', 'category': 'security', 'description': 'Security group for web traffic'}
            ],
            'config_fields': [
                {'name': 'vpc_cidr', 'type': 'text', 'label': 'VPC CIDR Block', 'required': True, 'default': '10.111.0.0/16', 'group': 'Network', 'helpText': 'CIDR block for the VPC'},
                {'name': 'public_subnet_cidr', 'type': 'text', 'label': 'Public Subnet CIDR', 'required': True, 'default': '10.111.1.0/24', 'group': 'Network', 'helpText': 'CIDR block for the public subnet'},
                {'name': 'private_subnet_cidr', 'type': 'text', 'label': 'Private Subnet CIDR', 'required': True, 'default': '10.111.2.0/24', 'group': 'Network', 'helpText': 'CIDR block for the private subnet'},
                {'name': 'region', 'type': 'select', 'label': 'AWS Region', 'required': True, 'default': 'us-east-1', 'group': 'General', 'helpText': 'AWS Region for deployment'}
            ]
        }

    def __init__(self, name=None, config=None, **kwargs):
        super().__init__(name, config or kwargs)
        self.namer = ResourceNamer(
            project=self.config.get('project', 'default'),
            environment=self.config.get('environment', 'prod'),
            region=self.config.get('region', 'us-east-1'),
            template='vpc-network'
        )

    def create_infrastructure(self):
        vpc = factory.create('aws:ec2:Vpc', 'MainVPC', 
            cidr_block=self.config.get('vpc_cidr', '10.111.0.0/16'),
            enable_dns_hostnames=True,
            enable_dns_support=True,
            tags=get_standard_tags(Name='production-vpc', Tier='prod')
        )

        public_subnet = factory.create('aws:ec2:Subnet', 'PublicSubnet',
            vpc_id=vpc.id,
            cidr_block=self.config.get('public_subnet_cidr', '10.111.1.0/24'),
            availability_zone=f'{self.config.get("region", "us-east-1")}a',
            map_public_ip_on_launch=True,
            tags=get_standard_tags(Name='public-subnet', Tier='public')
        )

        private_subnet = factory.create('aws:ec2:Subnet', 'PrivateSubnet',
            vpc_id=vpc.id,
            cidr_block=self.config.get('private_subnet_cidr', '10.111.2.0/24'),
            availability_zone=f'{self.config.get("region", "us-east-1")}a',
            tags=get_standard_tags(Name='private-subnet', Tier='private')
        )

        web_sg = factory.create('aws:ec2:SecurityGroup', 'WebSecurityGroup',
            vpc_id=vpc.id,
            description='Web tier - HTTP/HTTPS from internet',
            ingress=[
                {'from_port': 80, 'to_port': 80, 'protocol': 'tcp', 'cidr_blocks': ['0.0.0.0/0']},
                {'from_port': 443, 'to_port': 443, 'protocol': 'tcp', 'cidr_blocks': ['0.0.0.0/0']}
            ],
            egress=[{'from_port': 0, 'to_port': 0, 'protocol': '-1', 'cidr_blocks': ['0.0.0.0/0']}],
            tags=get_standard_tags(Name='web-sg')
        )

        internet_gateway = factory.create('aws:ec2:InternetGateway', 'MainIGW',
            vpc_id=vpc.id,
            tags=get_standard_tags(Name='main-igw')
        )

        route_table = factory.create('aws:ec2:RouteTable', 'PublicRouteTable',
            vpc_id=vpc.id,
            routes=[{'cidr_block': '0.0.0.0/0', 'gateway_id': internet_gateway.id}],
            tags=get_standard_tags(Name='public-rt')
        )

        aws.ec2.RouteTableAssociation('PublicSubnetAssociation',
            subnet_id=public_subnet.id,
            route_table_id=route_table.id
        )

        pulumi.export('vpc_id', vpc.id)
        pulumi.export('public_subnet_id', public_subnet.id)
        pulumi.export('private_subnet_id', private_subnet.id)