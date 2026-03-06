"""
EKS Template

Atomic template for deploying standalone AWS EKS Clusters directly (no ComponentResource wrapper).
Perfect for advanced users building custom Kubernetes architectures.
"""
from provisioner.templates.base import InfrastructureTemplate, template_registry
from typing import Any, Dict, List, Optional
import pulumi
import pulumi_aws as aws


@template_registry("aws-eks-atomic")
class EKSAtomicTemplate(InfrastructureTemplate):
    """
    EKS Cluster Template

    Deploys a standalone AWS EKS Cluster directly.
    Requires VPC subnet IDs and IAM role ARN.
    """
    @classmethod
    def get_metadata(cls):
        from provisioner.templates.base.template import TemplateMetadata, TemplateCategory
        return TemplateMetadata(
            name="aws-eks-atomic",
            description="Direct AWS EKS cluster deployment for custom Kubernetes infrastructures.",
            category=TemplateCategory.KUBERNETES,
            version="latest",
            author="InnovativeApps",
            tags=["aws", "eks", "kubernetes", "containers"],
            estimated_cost="$144/month",
            complexity="high",
            deployment_time="15-20m",
            is_listed_in_marketplace=False,
            title="AWS EKS Cluster (Atomic)"
        )

    def __init__(self, name: str, config: Dict[str, Any], **kwargs):
        super().__init__(name, config, **kwargs)
        self.template_name = "eks-atomic"
        self.cluster: Optional[aws.eks.Cluster] = None

    def create_infrastructure(self) -> Dict[str, Any]:
        """Create the EKS cluster infrastructure directly - shows as actual AWS resource in preview"""
        # Get configuration
        cluster_name = self.config.get("cluster_name", f"{self.name}")
        role_arn = self.config.get("role_arn")
        subnet_ids = self.config.get("subnet_ids", [])
        security_group_ids = self.config.get("security_group_ids", [])
        endpoint_private_access = self.config.get("endpoint_private_access", True)
        endpoint_public_access = self.config.get("endpoint_public_access", True)
        public_access_cidrs = self.config.get("public_access_cidrs", ["0.0.0.0/0"])
        version = self.config.get("version", "1.28")
        enabled_cluster_log_types = self.config.get("enabled_cluster_log_types", [
            "api", "audit", "authenticator", "controllerManager", "scheduler"
        ])
        
        if not role_arn:
            raise ValueError("role_arn is required for EKS cluster deployment")
        if not subnet_ids or len(subnet_ids) < 2:
            raise ValueError("At least 2 subnet IDs are required for EKS cluster deployment")

        tags = {
            "Name": cluster_name,
            "Project": self.config.get("project_name", "archie"),
            "Environment": self.config.get("environment", "dev"),
            "ManagedBy": "Archie"
        }

        # Create EKS Cluster directly (no ComponentResource wrapper)
        vpc_config_args = {
            "subnet_ids": subnet_ids,
            "endpoint_private_access": endpoint_private_access,
            "endpoint_public_access": endpoint_public_access,
            "public_access_cidrs": public_access_cidrs
        }
        if security_group_ids:
            vpc_config_args["security_group_ids"] = security_group_ids
            
        self.cluster = aws.eks.Cluster(
            f"{self.name}-cluster",
            name=cluster_name,
            role_arn=role_arn,
            vpc_config=vpc_config_args,
            version=version,
            enabled_cluster_log_types=enabled_cluster_log_types,
            tags=tags
        )

        return {
            "cluster_id": self.cluster.id,
            "cluster_arn": self.cluster.arn,
            "cluster_endpoint": self.cluster.endpoint,
            "cluster_version": self.cluster.version,
            "cluster_name": self.cluster.name,
            "cluster_security_group_id": self.cluster.vpc_config.cluster_security_group_id,
            "cluster_certificate_authority": self.cluster.certificate_authority
        }

    def get_outputs(self) -> Dict[str, Any]:
        """Return the outputs of the infrastructure"""
        if not self.cluster:
            raise RuntimeError("Infrastructure not created yet. Call create_infrastructure() first.")
        
        return {
            "cluster_id": self.cluster.id,
            "cluster_arn": self.cluster.arn,
            "cluster_endpoint": self.cluster.endpoint,
            "cluster_version": self.cluster.version,
            "cluster_name": self.cluster.name,
            "cluster_security_group_id": self.cluster.vpc_config.cluster_security_group_id,
            "cluster_certificate_authority": self.cluster.certificate_authority
        }
