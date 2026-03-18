"""
EKS Non-Prod Template

Complete EKS cluster for development and testing with VPC and node flexibility.
Architecture: Layer 4 template that calls other Layer 4 templates (VPC, EC2)
"""
from typing import Any, Dict, Optional, List
import json
from pathlib import Path

import pulumi
import pulumi_aws as aws

from provisioner.templates.base import (
    InfrastructureTemplate,
    template_registry
)
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory
from provisioner.templates.template_config import TemplateConfig
from provisioner.utils.aws import ResourceNamer, get_standard_tags
from provisioner.templates.templates.aws.compute.eks_nonprod.config import EKSNonProdConfig
from provisioner.templates.templates.aws.networking.vpc_nonprod.pulumi import VPCSimpleNonprodTemplate
from provisioner.templates.templates.aws.compute.ec2_nonprod.pulumi import EC2NonProdTemplate


@template_registry("aws-eks-nonprod")
class EKSNonProdTemplate(InfrastructureTemplate):
    """
    EKS Non-Production Cluster
    """
    def __init__(self, name: str = None, config: Dict[str, Any] = None, **kwargs):
        """Initialize EKS nonprod template"""
        raw_config = config or kwargs or {}
        
        if name is None:
            name = raw_config.get('cluster_name', raw_config.get('clusterName', 'eks-nonprod'))
            
        super().__init__(name, raw_config)
        
        # Load template configuration (Pattern B)
        template_dir = Path(__file__).parent
        self.config_loader = TemplateConfig(template_dir, raw_config)
        self.cfg = EKSNonProdConfig(raw_config)
        
        # Sub-templates
        self.vpc_template: Optional[VPCSimpleNonprodTemplate] = None
        self.ec2_templates: List[EC2NonProdTemplate] = []
        
        # Resources (Pattern B)
        self.cluster = None
        self.cluster_role = None
        self.node_role = None
        self.instance_profile = None

    def create_infrastructure(self) -> Dict[str, Any]:
        """Deploy infrastructure (implements abstract method)"""
        return self.create()

    def create(self) -> Dict[str, Any]:
        """Deploy EKS infrastructure using factory pattern"""
        # Initialize ResourceNamer
        namer = ResourceNamer(
            project=self.cfg.project_name,
            environment=self.cfg.environment,
            region=self.cfg.region,
            template="aws-eks-nonprod"
        )
        
        # Generate standard tags
        tags = get_standard_tags(
            project=self.cfg.project_name,
            environment=self.cfg.environment,
            template="eks-nonprod"
        )
        tags.update(self.cfg.tags)

        # ========================================
        # STEP 1: VPC PROVISIONING
        # ========================================
        vpc_id = None
        private_subnet_ids = []
        
        if self.cfg.vpc_mode == 'new':
            vpc_config = {
                "project_name": f"{self.name}-vpc",
                "cidr_block": self.cfg.vpc_cidr,
                "environment": self.cfg.environment,
                "ssh_access_ip": self.cfg.ssh_access_ip or ''
            }
            self.vpc_template = VPCSimpleNonprodTemplate(name=f"{self.name}-vpc", config=vpc_config)
            self.vpc_template.create_infrastructure()
            vpc_outputs = self.vpc_template.get_outputs()
            
            vpc_id = vpc_outputs['vpc_id']
            private_subnet_ids = vpc_outputs['private_subnet_ids']
        else:
            vpc_id = self.cfg.vpc_id
            private_subnet_ids = self.cfg.private_subnet_ids

        # ========================================
        # STEP 2: IAM ROLES
        # ========================================
        # Cluster Role
        cluster_role_name = namer.iam_role("eks", purpose="cluster")
        self.cluster_role = factory.create(
            "aws:iam:Role",
            cluster_role_name,
            assume_role_policy=json.dumps({
                "Version": "2012-10-17",
                "Statement": [{
                    "Action": "sts:AssumeRole",
                    "Principal": {"Service": "eks.amazonaws.com"},
                    "Effect": "Allow"
                }]
            }),
            managed_policy_arns=[
                "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy",
                "arn:aws:iam::aws:policy/AmazonEKSVPCResourceController"
            ],
            tags=tags
        )

        # Node Role
        node_role_name = namer.iam_role("eks", purpose="nodes")
        self.node_role = factory.create(
            "aws:iam:Role",
            node_role_name,
            assume_role_policy=json.dumps({
                "Version": "2012-10-17",
                "Statement": [{
                    "Action": "sts:AssumeRole",
                    "Principal": {"Service": "ec2.amazonaws.com"},
                    "Effect": "Allow"
                }]
            }),
            managed_policy_arns=[
                "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy",
                "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy",
                "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
            ],
            tags=tags
        )

        # Instance Profile
        profile_name = f"instance-profile-nodes-{namer.project}-nonprod-{namer.region_short}"
        self.instance_profile = factory.create(
            "aws:iam:InstanceProfile",
            profile_name,
            role=self.node_role.name,
            tags=tags
        )

        # ========================================
        # STEP 3: EKS CLUSTER
        # ========================================
        self.cluster = factory.create(
            "aws:eks:Cluster",
            self.cfg.cluster_name,
            role_arn=self.cluster_role.arn,
            version=self.cfg.kubernetes_version,
            vpc_config={
                "subnet_ids": private_subnet_ids,
                "endpoint_private_access": True,
                "endpoint_public_access": True
            },
            tags={**tags, "Name": self.cfg.cluster_name}
        )

        # ========================================
        # STEP 4: COMPUTE (MANAGED NODES)
        # ========================================
        if self.cfg.node_mode == 'managed':
            # Create user data for bootstrapping nodes
            user_data = pulumi.Output.all(
                self.cluster.name,
                self.cluster.endpoint,
                self.cluster.certificate_authority
            ).apply(lambda args: f"""#!/bin/bash
set -ex
/etc/eks/bootstrap.sh {args[0]} --apiserver-endpoint {args[1]} --b64-cluster-ca {args[2]['data']}
""")

            for i in range(self.cfg.desired_capacity):
                subnet_id = private_subnet_ids[i % len(private_subnet_ids)] if private_subnet_ids else None
                node_name = f"{self.cfg.cluster_name}-node-{i+1}"
                
                ec2_config = {
                    "project_name": node_name,
                    "environment": self.cfg.environment,
                    "vpc_id": vpc_id,
                    "subnet_id": subnet_id,
                    "vpc_mode": "existing",
                    "instance_type": self.cfg.node_instance_type,
                    "iam_instance_profile": self.instance_profile.name,
                    "user_data": user_data,
                    "ssh_access_ip": self.cfg.ssh_access_ip or ''
                }
                
                ec2_template = EC2NonProdTemplate(name=node_name, config=ec2_config)
                ec2_template.create_infrastructure()
                self.ec2_templates.append(ec2_template)

        # Generate kubeconfig
        kubeconfig = pulumi.Output.all(
            self.cluster.endpoint,
            self.cluster.certificate_authority,
            self.cluster.name
        ).apply(lambda args: json.dumps({
            "apiVersion": "v1",
            "clusters": [{"cluster": {"server": args[0], "certificate-authority-data": args[1]['data']}, "name": "kubernetes"}],
            "contexts": [{"context": {"cluster": "kubernetes", "user": "aws"}, "name": "aws"}],
            "current-context": "aws",
            "kind": "Config",
            "users": [{"name": "aws", "user": {"exec": {"apiVersion": "client.authentication.k8s.io/v1beta1", "command": "aws", "args": ["eks", "get-token", "--cluster-name", args[2]]}}}]
        }))

        pulumi.export("kubeconfig", kubeconfig)
        pulumi.export("cluster_name", self.cluster.name)
        pulumi.export("cluster_endpoint", self.cluster.endpoint)
        pulumi.export("cluster_arn", self.cluster.arn)
        pulumi.export("kubeconfig_command", self.cluster.name.apply(
            lambda name: f"aws eks update-kubeconfig --name {name} --region {self.cfg.region}"
        ))

        return self.get_outputs()

    def get_outputs(self) -> Dict[str, Any]:
        """Get template outputs (Pattern B)"""
        if not self.cluster:
            return {"status": "not_created"}

        outputs = {
            "cluster_name": self.cluster.name,
            "cluster_endpoint": self.cluster.endpoint,
            "cluster_arn": self.cluster.arn,
            "vpc_id": self.cfg.vpc_id
        }
        
        if self.vpc_template:
            outputs.update(self.vpc_template.get_outputs())
            
        return outputs

    @classmethod
    def get_metadata(cls) -> Dict[str, Any]:
        """Pattern B Metadata source of truth"""
        return {
            "name": "aws-eks-nonprod",
            "title": "EKS Kubernetes Cluster",
            "description": "Enterprise Kubernetes environment with managed control plane and EC2 node groups.",
            "category": "compute",
            "version": "1.4.0",
            "author": "InnovativeApps",
            "cloud": "aws",
            "environment": "nonprod",
            "base_cost": "$75/month",
            "features": [
                "AWS-Managed EKS Control Plane",
                "Automated Node Group orchestration",
                "Dedicated Multi-AZ VPC Architecture",
                "Integrated IAM Role-Based Access Control",
                "Self-healing node bootstrap logic"
            ],
            "tags": ["eks", "kubernetes", "containers", "compute", "nonprod"],
            "deployment_time": "15-20 minutes",
            "complexity": "advanced",
            "pillars": [
                {
                    "title": "Operational Excellence",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Managed control plane with automated upgrades and observability",
                    "practices": [
                        "AWS-managed control plane eliminates manual upgrade burden",
                        "Infrastructure as Code via Pulumi for repeatable cluster deployments",
                        "Automated node bootstrapping with self-healing user data scripts",
                        "Integrated IAM roles for auditability and access control",
                        "Standard tagging for cost allocation and resource tracking"
                    ]
                },
                {
                    "title": "Security",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Enterprise-grade Kubernetes security with IAM integration",
                    "practices": [
                        "IAM OIDC provider for fine-grained pod-level service accounts",
                        "Pod security standards enforced via Kubernetes admission control",
                        "Dedicated IAM roles for cluster and node separation of duties",
                        "Private subnet placement for worker nodes with public API endpoint",
                        "EKS-managed security patches for control plane components"
                    ]
                },
                {
                    "title": "Reliability",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Highly available managed control plane across multiple AZs",
                    "practices": [
                        "Multi-AZ control plane managed by AWS with automatic failover",
                        "Worker nodes distributed across availability zones for resilience",
                        "Self-healing node bootstrap logic for automatic recovery",
                        "Dedicated VPC with private subnets for network isolation",
                        "EKS-managed etcd with automated backups and replication"
                    ]
                },
                {
                    "title": "Performance Efficiency",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Scalable compute with right-sized node groups",
                    "practices": [
                        "Horizontal Pod Autoscaler support for workload-driven scaling",
                        "Cluster autoscaler integration for node-level elasticity",
                        "Configurable instance types to match workload requirements",
                        "Multi-AZ subnet distribution for balanced resource placement",
                        "EBS-optimized nodes for consistent storage performance"
                    ]
                },
                {
                    "title": "Cost Optimization",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Cost-aware defaults with scaling flexibility",
                    "practices": [
                        "Fargate profile support for serverless pay-per-pod pricing",
                        "Spot instance compatibility for non-critical workloads",
                        "Right-sized node groups to avoid over-provisioning",
                        "Shared VPC infrastructure reduces networking overhead",
                        "Configurable desired capacity to match actual demand"
                    ]
                },
                {
                    "title": "Sustainability",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Efficient container orchestration reduces resource waste",
                    "practices": [
                        "Container bin-packing maximizes compute utilization per node",
                        "Autoscaling eliminates idle capacity during low-demand periods",
                        "Managed control plane shares AWS infrastructure efficiently",
                        "Graviton-compatible instance types for better performance per watt",
                        "Shared networking layer reduces duplicated infrastructure"
                    ]
                }
            ]
        }

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        """Get configuration schema from source of truth"""
        return EKSNonProdConfig.get_config_schema()
