import pulumi
import pulumi_aws as aws
from provisioner.templates.base import InfrastructureTemplate, template_registry
from provisioner.utils.aws import ResourceNamer, get_standard_tags
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory

@template_registry("aws-basic-network")
class BasicNetworkTemplate(InfrastructureTemplate):
    def __init__(self, name=None, config=None, **kwargs):
        raw_config = config or kwargs or {}
        if name is None:
            name = raw_config.get('project_name', 'my-template')
        super().__init__(name, raw_config)

    def create_infrastructure(self):
        namer = ResourceNamer(
            project=self.config.get("project_name", "proj"),
            environment=self.config.get("environment", "prod"),
            region=self.config.get("region", "us-east-1"),
            template="basic-network"
        )

        vpc = factory.create("aws:ec2:Vpc", namer.name("vpc"), 
            cidr_block=self.config.get("vpc_cidr", "10.111.0.0/16"),
            enable_dns_support=True,
            enable_dns_hostnames=True,
            tags=get_standard_tags(name=namer.name("vpc"))
        )

        public_subnet = factory.create("aws:ec2:Subnet", namer.name("public-subnet"),
            vpc_id=vpc.id,
            cidr_block=self.config.get("public_subnet_cidr", "10.111.1.0/24"),
            availability_zone=self.config.get("availability_zone", "us-east-1a"),
            map_public_ip_on_launch=True,
            tags=get_standard_tags(name=namer.name("public-subnet"), tier="public")
        )

        private_subnet = factory.create("aws:ec2:Subnet", namer.name("private-subnet"),
            vpc_id=vpc.id,
            cidr_block=self.config.get("private_subnet_cidr", "10.111.2.0/24"),
            availability_zone=self.config.get("availability_zone", "us-east-1a"),
            tags=get_standard_tags(name=namer.name("private-subnet"), tier="private")
        )

        web_sg = factory.create("aws:ec2:SecurityGroup", namer.name("web-sg"),
            vpc_id=vpc.id,
            description="Web tier - HTTP/HTTPS from internet",
            ingress=[
                {"from_port": 80, "to_port": 80, "protocol": "tcp", "cidr_blocks": ["0.0.0.0/0"]},
                {"from_port": 443, "to_port": 443, "protocol": "tcp", "cidr_blocks": ["0.0.0.0/0"]}
            ],
            egress=[{"from_port": 0, "to_port": 0, "protocol": "-1", "cidr_blocks": ["0.0.0.0/0"]}],
            tags=get_standard_tags(name=namer.name("web-sg"))
        )

        igw = factory.create("aws:ec2:InternetGateway", namer.name("igw"),
            vpc_id=vpc.id,
            tags=get_standard_tags(name=namer.name("igw"))
        )

        route_table = factory.create("aws:ec2:RouteTable", namer.name("public-rt"),
            vpc_id=vpc.id,
            routes=[{"cidr_block": "0.0.0.0/0", "gateway_id": igw.id}],
            tags=get_standard_tags(name=namer.name("public-rt"))
        )

        rt_assoc = factory.create("aws:ec2:RouteTableAssociation", namer.name("public-rt-assoc"),
            subnet_id=public_subnet.id,
            route_table_id=route_table.id
        )

        pulumi.export("vpc_id", vpc.id)
        pulumi.export("public_subnet_id", public_subnet.id)
        pulumi.export("private_subnet_id", private_subnet.id)
        pulumi.export("web_security_group_id", web_sg.id)

        return self.get_outputs()

    def get_outputs(self):
        return {
            "vpc_id": pulumi.get_output("vpc_id"),
            "public_subnet_id": pulumi.get_output("public_subnet_id"),
            "private_subnet_id": pulumi.get_output("private_subnet_id"),
            "web_security_group_id": pulumi.get_output("web_security_group_id")
        }

    @classmethod
    def get_metadata(cls):
        return {
            "type": "networking",
            "name": "AWS Basic Network",
            "description": "Creates a basic VPC with public and private subnets, internet gateway, and web security group",
            "version": "1.0.0"
        }
