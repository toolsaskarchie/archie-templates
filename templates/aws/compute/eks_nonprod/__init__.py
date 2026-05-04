"""EKS Non-Production Cluster Template"""

from provisioner.templates.templates.aws.compute.eks_nonprod.pulumi import EKSNonProdTemplate
from provisioner.templates.templates.aws.compute.eks_nonprod.config import EKSNonProdConfig

__all__ = ['EKSNonProdTemplate', 'EKSNonProdConfig']
