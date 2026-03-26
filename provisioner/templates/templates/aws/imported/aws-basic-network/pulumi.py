import pulumi
import pulumi_aws as aws
from archie.core import InfrastructureTemplate, TemplateConfig
from archie.cloud.aws.factories import PulumiAtomicFactory
from archie.utils import ResourceNamer, get_standard_tags

@template_registry("aws-basic-network")
class AWSBasicNetworkTemplate(InfrastructureTemplate):
    @classmethod
    def get_metadata(cls):
        return {
            "name": "aws-basic-network",
            "title": "Basic AWS Network Setup",
            "description": "Creates a basic VPC with public subnet and web security group",
            "cloud": "aws",
            "category": "networking",
            "tier": "standard",
            "estimated_cost": "$0-5/mo",
            "deployment_time": "~5 min"
        }

    def _deploy(self, config: TemplateConfig):
        namer = ResourceNamer(self.name)
        tags = get_standard_tags()

        vpc = aws.ec2.Vpc(
            namer.create("main-vpc"),
            cidr_block=config.get_string("vpc_cidr_block", default="10.0.0.0/16"),
            enable_dns_support=True,
            enable_dns_hostnames=True,
            tags={**tags, "Name": "production-vpc", "Environment": "prod"}
        )

        public_subnet = aws.ec2.Subnet(
            namer.create("public-subnet"),
            vpc_id=vpc.id,
            cidr_block=config.get_string("public_subnet_cidr", default="10.0.1.0/24"),
            availability_zone=config.get_string("availability_zone", default="us-east-1a"),
            map_public_ip_on_launch=True,
            tags={**tags, "Name": "public-subnet", "Tier": "public"}
        )

        web_sg = aws.ec2.SecurityGroup(
            namer.create("web-sg"),
            vpc_id=vpc.id,
            description="Web tier security group",
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
            tags={**tags, "Name": "web-sg"}
        )

        return {
            "vpc_id": vpc.id,
            "subnet_id": public_subnet.id,
            "security_group_id": web_sg.id
        }