import pulumi
import pulumi_aws as aws
from provisioner.templates.base import InfrastructureTemplate, template_registry
from provisioner.utils.aws import ResourceNamer, get_standard_tags
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory

@template_registry("aws-basic-network")
class AWSBasicNetworkTemplate(InfrastructureTemplate):
    def __init__(self, name=None, config=None, **kwargs):
        super().__init__(name, config or kwargs)
        self.namer = ResourceNamer(
            project=self.config.get('project', 'default'),
            environment=self.config.get('environment', 'prod'),
            region=self.config.get('region', 'us-east-1'),
            template='basic-network'
        )

    def create_infrastructure(self):
        # VPC
        vpc = factory.create('aws:ec2:Vpc', self.namer.create('vpc'), {
            'cidrBlock': self.config.get('vpc_cidr', '10.111.0.0/16'),
            'enableDnsSupport': True,
            'enableDnsHostnames': True,
            'tags': get_standard_tags({
                'Name': 'production-vpc',
                'Environment': 'prod'
            })
        })

        # Public Subnet
        public_subnet = factory.create('aws:ec2:Subnet', self.namer.create('public-subnet'), {
            'vpcId': vpc.id,
            'cidrBlock': self.config.get('public_subnet_cidr', '10.111.1.0/24'),
            'availabilityZone': self.config.get('availability_zone', 'us-east-1a'),
            'mapPublicIpOnLaunch': True,
            'tags': get_standard_tags({
                'Name': 'public-subnet',
                'Tier': 'public'
            })
        })

        # Private Subnet
        private_subnet = factory.create('aws:ec2:Subnet', self.namer.create('private-subnet'), {
            'vpcId': vpc.id,
            'cidrBlock': self.config.get('private_subnet_cidr', '10.111.2.0/24'),
            'availabilityZone': self.config.get('availability_zone', 'us-east-1a'),
            'tags': get_standard_tags({
                'Name': 'private-subnet',
                'Tier': 'private'
            })
        })

        # Security Group
        web_sg = factory.create('aws:ec2:SecurityGroup', self.namer.create('web-sg'), {
            'vpcId': vpc.id,
            'description': 'Web tier - HTTP/HTTPS from internet',
            'ingress': [
                {
                    'fromPort': 80,
                    'toPort': 80,
                    'protocol': 'tcp',
                    'cidrBlocks': ['0.0.0.0/0']
                },
                {
                    'fromPort': 443,
                    'toPort': 443,
                    'protocol': 'tcp',
                    'cidrBlocks': ['0.0.0.0/0']
                }
            ],
            'egress': [{
                'fromPort': 0,
                'toPort': 0,
                'protocol': '-1',
                'cidrBlocks': ['0.0.0.0/0']
            }],
            'tags': get_standard_tags({
                'Name': 'web-sg'
            })
        })

        # Internet Gateway
        igw = factory.create('aws:ec2:InternetGateway', self.namer.create('igw'), {
            'vpcId': vpc.id,
            'tags': get_standard_tags({
                'Name': 'main-igw'
            })
        })

        # Route Table
        route_table = factory.create('aws:ec2:RouteTable', self.namer.create('public-rt'), {
            'vpcId': vpc.id,
            'routes': [{
                'cidrBlock': '0.0.0.0/0',
                'gatewayId': igw.id
            }],
            'tags': get_standard_tags({
                'Name': 'public-rt'
            })
        })

        # Route Table Association
        factory.create('aws:ec2:RouteTableAssociation', self.namer.create('public-rta'), {
            'subnetId': public_subnet.id,
            'routeTableId': route_table.id
        })

        # Exports
        pulumi.export('vpc_id', vpc.id)
        pulumi.export('public_subnet_id', public_subnet.id)
        pulumi.export('private_subnet_id', private_subnet.id)
        pulumi.export('web_security_group_id', web_sg.id)

    @classmethod
    def get_metadata(cls):
        return {
            'name': 'aws-basic-network',
            'title': 'AWS Basic Network',
            'description': 'Basic AWS network with public and private subnets, internet gateway, and security group',
            'category': 'networking',
            'cloud': 'aws',
            'tier': 'standard',
            'estimated_cost': '$0-10/mo',
            'deployment_time': '~5 min',
            'features': ['vpc', 'subnets', 'internet_gateway', 'route_table'],
            'use_cases': ['web_hosting', 'development_environments', 'basic_infrastructure'],
            'pillars': ['reliability', 'performance_efficiency', 'security'],
            'resources': [
                {'name': 'VPC', 'type': 'aws:ec2:Vpc', 'category': 'network', 'description': 'Main VPC for network'},
                {'name': 'Public Subnet', 'type': 'aws:ec2:Subnet', 'category': 'network', 'description': 'Public subnet for internet-facing resources'},
                {'name': 'Private Subnet', 'type': 'aws:ec2:Subnet', 'category': 'network', 'description': 'Private subnet for internal resources'},
                {'name': 'Web Security Group', 'type': 'aws:ec2:SecurityGroup', 'category': 'security', 'description': 'Security group for web traffic'}
            ],
            'config_fields': [
                {'name': 'vpc_cidr', 'type': 'text', 'label': 'VPC CIDR Block', 'required': False, 'default': '10.111.0.0/16', 'group': 'Network', 'helpText': 'CIDR block for the VPC'},
                {'name': 'public_subnet_cidr', 'type': 'text', 'label': 'Public Subnet CIDR', 'required': False, 'default': '10.111.1.0/24', 'group': 'Network', 'helpText': 'CIDR block for public subnet'},
                {'name': 'private_subnet_cidr', 'type': 'text', 'label': 'Private Subnet CIDR', 'required': False, 'default': '10.111.2.0/24', 'group': 'Network', 'helpText': 'CIDR block for private subnet'},
                {'name': 'availability_zone', 'type': 'select', 'label': 'Availability Zone', 'required': False, 'default': 'us-east-1a', 'group': 'Network', 'helpText': 'AWS Availability Zone', 'options': ['us-east-1a', 'us-east-1b', 'us-east-1c', 'us-east-1d', 'us-east-1e', 'us-east-1f']}
            ]
        }
