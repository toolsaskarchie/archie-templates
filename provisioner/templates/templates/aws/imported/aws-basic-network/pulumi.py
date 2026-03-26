import pulumi
import pulumi_aws as aws
from provisioner.templates.base import InfrastructureTemplate, template_registry
from provisioner.utils.aws import ResourceNamer, get_standard_tags
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory

@template_registry("aws-basic-network")
class BasicNetworkTemplate(InfrastructureTemplate):
    @classmethod
    def get_metadata(cls):
        return {
            "name": "aws-basic-network",
            "title": "Basic AWS Network",
            "description": "Creates a VPC with public and private subnets, internet gateway, and security group",
            "category": "networking",
            "cloud": "aws",
            "tier": "standard",
            "estimated_cost": "$0-10/mo",
            "deployment_time": "~5 min",
            "features": ["VPC", "Public Subnet", "Private Subnet", "Internet Gateway"],
            "use_cases": ["Web Application Hosting", "Development Environments"],
            "pillars": ["security", "network"],
            "resources": [
                {"name": "VPC", "type": "aws:ec2:Vpc", "category": "networking", "description": "Main VPC for network isolation"},
                {"name": "Public Subnet", "type": "aws:ec2:Subnet", "category": "networking", "description": "Subnet with internet access"},
                {"name": "Private Subnet", "type": "aws:ec2:Subnet", "category": "networking", "description": "Isolated subnet without direct internet access"},
                {"name": "Web Security Group", "type": "aws:ec2:SecurityGroup", "category": "security", "description": "Allows HTTP/HTTPS traffic"},
                {"name": "Internet Gateway", "type": "aws:ec2:InternetGateway", "category": "networking", "description": "Enables internet connectivity"},
                {"name": "Public Route Table", "type": "aws:ec2:RouteTable", "category": "networking", "description": "Routes traffic for public subnet"}
            ],
            "config_fields": [
                {"name": "vpc_cidr", "type": "text", "label": "VPC CIDR Block", "required": true, "default": "10.111.0.0/16", "group": "Network", "helpText": "CIDR block for the VPC"},
                {"name": "public_subnet_cidr", "type": "text", "label": "Public Subnet CIDR", "required": true, "default": "10.111.1.0/24", "group": "Network", "helpText": "CIDR block for public subnet"},
                {"name": "private_subnet_cidr", "type": "text", "label": "Private Subnet CIDR", "required": true, "default": "10.111.2.0/24", "group": "Network", "helpText": "CIDR block for private subnet"},
                {"name": "availability_zone", "type": "text", "label": "Availability Zone", "required": true, "default": "us-east-1a", "group": "Network", "helpText": "AWS Availability Zone"}
            ]
        }

    def __init__(self, name=None, config=None, **kwargs):
        super().__init__(name, config or kwargs)
        self.namer = ResourceNamer(project=self.config.get("project", "default"), 
                                   environment=self.config.get("environment", "dev"), 
                                   region=self.config.get("region", "us-east-1"), 
                                   template="basic-network")

    def create_infrastructure(self):
        vpc = factory.create("aws:ec2:Vpc", self.namer.resource("vpc"), {
            "cidrBlock": self.config.get("vpc_cidr", "10.111.0.0/16"),
            "enableDnsSupport": True,
            "enableDnsHostnames": True,
            "tags": get_standard_tags({"Name": self.namer.resource("vpc"), "Tier": "network"})
        })

        public_subnet = factory.create("aws:ec2:Subnet", self.namer.resource("public-subnet"), {
            "vpcId": vpc.id,
            "cidrBlock": self.config.get("public_subnet_cidr", "10.111.1.0/24"),
            "availabilityZone": self.config.get("availability_zone", "us-east-1a"),
            "mapPublicIpOnLaunch": True,
            "tags": get_standard_tags({"Name": self.namer.resource("public-subnet"), "Tier": "public"})
        })

        private_subnet = factory.create("aws:ec2:Subnet", self.namer.resource("private-subnet"), {
            "vpcId": vpc.id,
            "cidrBlock": self.config.get("private_subnet_cidr", "10.111.2.0/24"),
            "availabilityZone": self.config.get("availability_zone", "us-east-1a"),
            "tags": get_standard_tags({"Name": self.namer.resource("private-subnet"), "Tier": "private"})
        })

        web_sg = factory.create("aws:ec2:SecurityGroup", self.namer.resource("web-sg"), {
            "vpcId": vpc.id,
            "description": "Web tier - HTTP/HTTPS from internet",
            "ingress": [
                {"fromPort": 80, "toPort": 80, "protocol": "tcp", "cidrBlocks": ["0.0.0.0/0"]},
                {"fromPort": 443, "toPort": 443, "protocol": "tcp", "cidrBlocks": ["0.0.0.0/0"]}
            ],
            "egress": [{
                "fromPort": 0, "toPort": 0, "protocol": "-1", "cidrBlocks": ["0.0.0.0/0"]
            }],
            "tags": get_standard_tags({"Name": self.namer.resource("web-sg"), "Tier": "security"})
        })

        igw = factory.create("aws:ec2:InternetGateway", self.namer.resource("igw"), {
            "vpcId": vpc.id,
            "tags": get_standard_tags({"Name": self.namer.resource("igw")})
        })

        route_table = factory.create("aws:ec2:RouteTable", self.namer.resource("public-rt"), {
            "vpcId": vpc.id,
            "routes": [{
                "cidrBlock": "0.0.0.0/0",
                "gatewayId": igw.id
            }],
            "tags": get_standard_tags({"Name": self.namer.resource("public-rt")})
        })

        route_assoc = factory.create("aws:ec2:RouteTableAssociation", self.namer.resource("public-rt-assoc"), {
            "subnetId": public_subnet.id,
            "routeTableId": route_table.id
        })

        pulumi.export("vpc_id", vpc.id)
        pulumi.export("public_subnet_id", public_subnet.id)
        pulumi.export("private_subnet_id", private_subnet.id)
        pulumi.export("web_security_group_id", web_sg.id)
