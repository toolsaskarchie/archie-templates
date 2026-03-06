"""EC2 Non-Production Instance Template"""
from provisioner.templates.templates.aws.compute.ec2_nonprod.pulumi import EC2NonProdTemplate
from provisioner.templates.templates.aws.compute.ec2_nonprod.config import EC2NonProdConfig
__all__ = ['EC2NonProdTemplate', 'EC2NonProdConfig']