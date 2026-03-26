import pulumi
import pulumi_aws as aws
from provisioner.templates.base import InfrastructureTemplate, template_registry
from provisioner.utils.aws import ResourceNamer, get_standard_tags
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory

@template_registry("aws-vpc-networking")
class AwsVpcNetworking(InfrastructureTemplate):
    def __init__(self, name=None, config=None, **kwargs):
        raw_config = config or kwargs or {}
        if name is None:
            name = raw_config.get('project_name', 'aws-vpc')
        super().__init__(name, raw_config)

    def create_infrastructure(self):
        # Config values nested in parameters — check both levels (Rule #6)
        params = self.config.get('parameters', {})
        def cfg(key, default=None):
            return self.config.get(key) or params.get(key) or default

        project = cfg('project_name', 'proj')
        env = cfg('environment', 'prod')
        region = cfg('region', 'us-east-1')
        tags = get_standard_tags(project=project, environment=env, template='aws-vpc-networking')

        self.vpc = factory.create('aws:ec2:Vpc', f'vpc-{project}-{env}',
            cidr_block=cfg('vpc_cidr', '10.111.0.0/16'),
            enable_dns_support=True,
            enable_dns_hostnames=True,
            tags={**tags, 'Name': f'vpc-{project}-{env}'}
        )

        self.public_subnet = factory.create('aws:ec2:Subnet', f'public-subnet-{project}-{env}',
            vpc_id=self.vpc.id,
            cidr_block=cfg('public_subnet_cidr', '10.111.1.0/24'),
            availability_zone=cfg('availability_zone', 'us-east-1a'),
            map_public_ip_on_launch=True,
            tags={**tags, 'Name': 'public-subnet', 'Tier': 'public'}
        )

        self.private_subnet = factory.create('aws:ec2:Subnet', f'private-subnet-{project}-{env}',
            vpc_id=self.vpc.id,
            cidr_block=cfg('private_subnet_cidr', '10.111.2.0/24'),
            availability_zone=cfg('availability_zone', 'us-east-1a'),
            tags={**tags, 'Name': 'private-subnet', 'Tier': 'private'}
        )

        self.web_sg = factory.create('aws:ec2:SecurityGroup', f'web-sg-{project}-{env}',
            vpc_id=self.vpc.id,
            description='Web tier - HTTP/HTTPS from internet',
            ingress=[
                {'from_port': 80, 'to_port': 80, 'protocol': 'tcp', 'cidr_blocks': ['0.0.0.0/0']},
                {'from_port': 443, 'to_port': 443, 'protocol': 'tcp', 'cidr_blocks': ['0.0.0.0/0']}
            ],
            egress=[{'from_port': 0, 'to_port': 0, 'protocol': '-1', 'cidr_blocks': ['0.0.0.0/0']}],
            tags={**tags, 'Name': 'web-sg'}
        )

        self.internet_gateway = factory.create('aws:ec2:InternetGateway', f'igw-{project}-{env}',
            vpc_id=self.vpc.id,
            tags={**tags, 'Name': 'main-igw'}
        )

        self.route_table = factory.create('aws:ec2:RouteTable', f'rt-public-{project}-{env}',
            vpc_id=self.vpc.id,
            routes=[{
                'cidr_block': '0.0.0.0/0',
                'gateway_id': self.internet_gateway.id
            }],
            tags={**tags, 'Name': 'public-rt'}
        )

        self.route_table_association = factory.create('aws:ec2:RouteTableAssociation', f'rta-public-{project}-{env}',
            subnet_id=self.public_subnet.id,
            route_table_id=self.route_table.id
        )

        pulumi.export('vpc_id', self.vpc.id)
        pulumi.export('public_subnet_id', self.public_subnet.id)
        pulumi.export('private_subnet_id', self.private_subnet.id)
        pulumi.export('web_sg_id', self.web_sg.id)

        return self.get_outputs()

    def get_outputs(self):
        return {
            'vpc_id': self.vpc.id if hasattr(self, 'vpc') else None,
            'public_subnet_id': self.public_subnet.id if hasattr(self, 'public_subnet') else None,
            'private_subnet_id': self.private_subnet.id if hasattr(self, 'private_subnet') else None,
            'web_sg_id': self.web_sg.id if hasattr(self, 'web_sg') else None
        }

    @classmethod
    def get_metadata(cls):
        return {
            'name': 'aws-vpc-networking',
            'title': 'AWS VPC with Public and Private Subnets',
            'description': 'Create a VPC with public and private subnets, internet gateway, route table, and security group',
            'category': 'networking',
            'cloud': 'aws',
            'tier': 'standard'
        }
