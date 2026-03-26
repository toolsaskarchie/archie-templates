import pulumi
import pulumi_aws as aws
from provisioner.templates.base import InfrastructureTemplate, template_registry
from provisioner.utils.aws import ResourceNamer, get_standard_tags
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory

@template_registry("aws-network-standard")
class NetworkTemplate(InfrastructureTemplate):
    def __init__(self, name=None, config=None, **kwargs):
        raw_config = config or kwargs or {}
        if name is None:
            name = raw_config.get('project_name', 'network-template')
        super().__init__(name, raw_config)

    def create_infrastructure(self):
        namer = ResourceNamer(
            project=self.config.get("project_name", "proj"),
            environment=self.config.get("environment", "prod"),
            region=self.config.get("region", "us-east-1"),
            template="network"
        )

        # Create VPC
        vpc = factory.create("aws:ec2:Vpc", namer.name("vpc"),
            cidr_block=self.config.get("vpc_cidr", "10.111.0.0/16"),
            enable_dns_support=True,
            enable_dns_hostnames=True,
            tags=get_standard_tags(Name="production-vpc")
        )

        # Create Public Subnet
        public_subnet = factory.create("aws:ec2:Subnet", namer.name("public-subnet"),
            vpc_id=vpc.id,
            cidr_block=self.config.get("public_subnet_cidr", "10.111.1.0/24"),
            availability_zone=self.config.get("availability_zone", "us-east-1a"),
            map_public_ip_on_launch=True,
            tags=get_standard_tags(Name="public-subnet", Tier="public")
        )

        # Create Private Subnet
        private_subnet = factory.create("aws:ec2:Subnet", namer.name("private-subnet"),
            vpc_id=vpc.id,
            cidr_block=self.config.get("private_subnet_cidr", "10.111.2.0/24"),
            availability_zone=self.config.get("availability_zone", "us-east-1a"),
            tags=get_standard_tags(Name="private-subnet", Tier="private")
        )

        # Create Web Security Group
        web_sg = factory.create("aws:ec2:SecurityGroup", namer.name("web-sg"),
            vpc_id=vpc.id,
            description="Web tier - HTTP/HTTPS from internet",
            ingress=[
                {
                    "from_port": 80,
                    "to_port": 80,
                    "protocol": "tcp",
                    "cidr_blocks": ["0.0.0.0/0"]
                },
                {
                    "from_port": 443,
                    "to_port": 443,
                    "protocol": "tcp",
                    "cidr_blocks": ["0.0.0.0/0"]
                }
            ],
            egress=[
                {
                    "from_port": 0,
                    "to_port": 0,
                    "protocol": "-1",
                    "cidr_blocks": ["0.0.0.0/0"]
                }
            ],
            tags=get_standard_tags(Name="web-sg")
        )

        # Create Internet Gateway
        igw = factory.create("aws:ec2:InternetGateway", namer.name("igw"),
            vpc_id=vpc.id,
            tags=get_standard_tags(Name="main-igw")
        )

        # Create Public Route Table
        public_rt = factory.create("aws:ec2:RouteTable", namer.name("public-rt"),
            vpc_id=vpc.id,
            routes=[
                {
                    "cidr_block": "0.0.0.0/0",
                    "gateway_id": igw.id
                }
            ],
            tags=get_standard_tags(Name="public-rt")
        )

        # Create Route Table Association
        factory.create("aws:ec2:RouteTableAssociation", namer.name("public-rta"),
            subnet_id=public_subnet.id,
            route_table_id=public_rt.id
        )

        return self.get_outputs()

    def get_outputs(self):
        outputs = {
            "vpc_id": self.resources.get("vpc", {}).get("id"),
            "public_subnet_id": self.resources.get("public-subnet", {}).get("id"),
            "private_subnet_id": self.resources.get("private-subnet", {}).get("id"),
            "web_security_group_id": self.resources.get("web-sg", {}).get("id")
        }
        for key, value in outputs.items():
            pulumi.export(key, value)
        return outputs

    @classmethod
    def get_metadata(cls):
        return {
            "name": "aws-network-standard",
            "title": "AWS Standard Network Architecture",
            "description": "Creates a standard AWS VPC with public and private subnets, internet gateway, and web security group",
            "category": "networking",
            "cloud": "aws",
            "tier": "standard",
            "estimated_cost": "$0-10/mo",
            "deployment_time": "~5 min",
            "features": ["VPC", "Public Subnet", "Private Subnet", "Internet Gateway"],
            "use_cases": ["Web Applications", "Cloud Infrastructure"],
            "pillars": ["Network Isolation", "Security"],
            "resources": [
                {"name": "VPC", "type": "aws:ec2:Vpc", "category": "networking", "description": "Primary network container"},
                {"name": "Public Subnet", "type": "aws:ec2:Subnet", "category": "networking", "description": "Subnet with internet access"},
                {"name": "Private Subnet", "type": "aws:ec2:Subnet", "category": "networking", "description": "Subnet without direct internet access"},
                {"name": "Web Security Group", "type": "aws:ec2:SecurityGroup", "category": "security", "description": "Firewall rules for web traffic"}
            ],
            "config_fields": [
                {"name": "project_name", "type": "text", "label": "Project Name", "required": true, "default": "my-project", "group": "General", "helpText": "Name of the project"},
                {"name": "environment", "type": "select", "label": "Environment", "required": true, "default": "prod", "group": "General", "options": ["dev", "staging", "prod"], "helpText": "Deployment environment"},
                {"name": "region", "type": "select", "label": "AWS Region", "required": true, "default": "us-east-1", "group": "Network", "options": ["us-east-1", "us-east-2", "us-west-1", "us-west-2"], "helpText": "AWS region for deployment"},
                {"name": "vpc_cidr", "type": "text", "label": "VPC CIDR Block", "required": true, "default": "10.111.0.0/16", "group": "Network", "helpText": "CIDR block for the VPC"},
                {"name": "public_subnet_cidr", "type": "text", "label": "Public Subnet CIDR", "required": true, "default": "10.111.1.0/24", "group": "Network", "helpText": "CIDR block for the public subnet"},
                {"name": "private_subnet_cidr", "type": "text", "label": "Private Subnet CIDR", "required": true, "default": "10.111.2.0/24", "group": "Network", "helpText": "CIDR block for the private subnet"},
                {"name": "availability_zone", "type": "select", "label": "Availability Zone", "required": true, "default": "us-east-1a", "group": "Network", "options": ["us-east-1a", "us-east-1b", "us-east-1c"], "helpText": "AWS availability zone"}
            ]
        }
