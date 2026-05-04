"""EC2 Production Instance Template"""
from provisioner.templates.templates.aws.compute.ec2_prod.pulumi import EC2ProdTemplate
from provisioner.templates.templates.aws.compute.ec2_prod.config import EC2ProdConfig
__all__ = ['EC2ProdTemplate', 'EC2ProdConfig']