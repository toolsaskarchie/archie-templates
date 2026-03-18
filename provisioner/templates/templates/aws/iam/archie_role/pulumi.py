"""
Archie Cross-Account Role Template

Creates an IAM role that Archie can assume to deploy infrastructure in your AWS account.
This is the secure, recommended way to give Archie access without sharing long-term credentials.
"""
from typing import Any, Dict, Optional
import pulumi
import pulumi_aws as aws
import json

# Import Archie utils for consistent patterns
from provisioner.utils.aws import (
    ResourceNamer,
    get_standard_tags
)
from provisioner.templates.base import template_registry, InfrastructureTemplate
from provisioner.templates.templates.aws.iam.archie_role.config import ArchieRoleConfig
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory


@template_registry("aws-archie-role")
class ArchieRoleTemplate(InfrastructureTemplate):
    """
    Archie Cross-Account Role Template - Pattern B Implementation
    
    Creates:
    - IAM Policy with restricted ReadOnly permissions
    - IAM Role with trust relationship to Archie account
    """

    def __init__(self, name: str = None, config: Dict[str, Any] = None, **kwargs):
        """Initialize Archie role template"""
        raw_config = config or kwargs or {}
        
        if name is None:
            name = raw_config.get('projectName') or raw_config.get('project_name', 'archie-role')
        
        super().__init__(name, raw_config)
        self.cfg = ArchieRoleConfig(raw_config)
        self.role: Optional[aws.iam.Role] = None
        self.policy: Optional[aws.iam.Policy] = None
        
        self._validate_config()
    
    def _validate_config(self) -> None:
        """Validate configuration"""
        if not self.cfg.archie_account_id:
            raise ValueError("archieAccountId is required")
        
        if not self.cfg.external_id:
            raise ValueError("externalId is required")
    
    def create_infrastructure(self) -> Dict[str, Any]:
        """Deploy infrastructure (implements abstract method)"""
        return self.create()

    def create(self) -> Dict[str, Any]:
        """Deploy Archie role using factory pattern"""
        
        environment = self.cfg.environment or 'nonprod'
        region = self.cfg.region or 'us-east-1'
        
        # Tags
        tags = get_standard_tags(
            project=self.cfg.project_name,
            environment=environment,
            template="aws-archie-role"
        )
        tags.update(self.cfg.tags)
        
        # Trust policy
        trust_policy = {
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": {
                    "AWS": f"arn:aws:iam::{self.cfg.archie_account_id}:root"
                },
                "Action": "sts:AssumeRole",
                "Condition": {
                    "StringEquals": {
                        "sts:ExternalId": self.cfg.external_id
                    }
                }
            }]
        }
        
        # Restricted ReadOnly Policy
        read_only_policy_doc = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "ec2:Describe*",
                        "s3:List*",
                        "s3:Get*",
                        "rds:Describe*",
                        "elasticloadbalancing:Describe*",
                        "autoscaling:Describe*",
                        "cloudwatch:Describe*",
                        "cloudwatch:Get*",
                        "cloudwatch:List*",
                        "logs:Describe*",
                        "logs:Get*",
                        "logs:List*",
                        "iam:List*",
                        "iam:Get*",
                        "sns:List*",
                        "sns:Get*",
                        "sqs:List*",
                        "sqs:Get*",
                        "route53:List*",
                        "route53:Get*"
                    ],
                    "Resource": "*"
                }
            ]
        }
        
        # 1. Create Policy
        self.policy = factory.create(
            "aws:iam:Policy",
            f"{self.name}-policy",
            name=f"pol-archierole-{self.cfg.project_name}-{environment}-{region}",
            description="Restricted ReadOnly policy for Archie connection",
            policy=json.dumps(read_only_policy_doc),
            tags=tags,
        )

        # 2. Create Role
        self.role = factory.create(
            "aws:iam:Role",
            self.name,
            name=f"role-archie-{self.cfg.project_name}-{environment}-{region}",
            assume_role_policy=json.dumps(trust_policy),
            managed_policy_arns=[self.policy.arn],
            tags=tags,
            opts=pulumi.ResourceOptions(depends_on=[self.policy]),
        )
        
        # Export outputs
        pulumi.export("role_arn", self.role.arn)
        pulumi.export("role_name", self.role.name)
        pulumi.export("external_id", self.cfg.external_id)
        
        return self.get_outputs()

    def get_outputs(self) -> Dict[str, Any]:
        """Get template outputs"""
        if not self.role:
            return {}
        
        return {
            "role_arn": self.role.arn,
            "role_name": self.role.name,
            "role_id": self.role.id,
            "policy_arn": self.policy.arn if self.policy else None,
            "external_id": self.cfg.external_id,
            "archie_account_id": self.cfg.archie_account_id
        }

    @classmethod
    def get_metadata(cls) -> Dict[str, Any]:
        """Template metadata for marketplace registration"""
        return {
            "name": "aws-archie-role",
            "title": "Archie Cross-Account Role",
            "description": "Secure, managed IAM role for connecting your AWS account to Archie. Implements the principle of least privilege using restricted read-only permissions and STS External ID verification.",
            "category": "security",
            "version": "1.0.0",
            "author": "InnovativeApps",
            "cloud": "aws",
            "environment": "all",
            "base_cost": "$0.00/month",
            "tags": ["iam", "role", "security", "connection", "managed"],
            "features": [
                "Secure Cross-Account Trust Policy",
                "Mandatory STS External ID Verification",
                "Restricted Read-Only permissions for discovery",
                "Automated Customer Managed Policy creation",
                "No long-term credentials or access keys required"
            ],
            "deployment_time": "1-2 minutes",
            "complexity": "low",
            "pillars": [
                {
                    "title": "Operational Excellence",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Fully automated IAM provisioning with infrastructure as code",
                    "practices": [
                        "Infrastructure as Code for repeatable role deployments",
                        "Automated policy lifecycle management via Pulumi",
                        "Standard tagging for governance and resource tracking",
                        "Consistent naming conventions for cross-account roles",
                        "One-click deployment eliminates manual IAM configuration"
                    ]
                },
                {
                    "title": "Security",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Industry-standard cross-account trust with least privilege",
                    "practices": [
                        "STS External ID prevents confused deputy attacks",
                        "Restricted read-only permissions follow least privilege principle",
                        "Cross-account trust eliminates long-term access key exposure",
                        "Customer Managed Policy for granular permission control",
                        "No root or admin-level permissions granted"
                    ]
                },
                {
                    "title": "Reliability",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "IAM is a globally resilient AWS service with no downtime",
                    "practices": [
                        "IAM is a global service with built-in multi-region redundancy",
                        "Role assumption is stateless and inherently reliable",
                        "No infrastructure dependencies that could cause failures",
                        "Automated deployment reduces human error in configuration",
                        "External ID validation prevents unauthorized access attempts"
                    ]
                },
                {
                    "title": "Performance Efficiency",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Zero-overhead identity federation with instant provisioning",
                    "practices": [
                        "IAM role assumption adds no latency to API operations",
                        "No compute resources required for credential management",
                        "STS tokens are cached and reused efficiently",
                        "Read-only scoped permissions minimize API call overhead",
                        "Deploys in under 2 minutes with no warm-up required"
                    ]
                },
                {
                    "title": "Cost Optimization",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "IAM roles and policies are completely free",
                    "practices": [
                        "IAM roles and policies incur zero AWS charges",
                        "Eliminates need for bastion hosts or VPN infrastructure",
                        "No compute or storage costs for credential management",
                        "STS temporary credentials are free to generate",
                        "Replaces costly long-term credential rotation processes"
                    ]
                },
                {
                    "title": "Sustainability",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Serverless identity service with minimal resource footprint",
                    "practices": [
                        "No compute resources provisioned or running",
                        "Leverages shared AWS IAM infrastructure globally",
                        "Zero energy consumption for credential storage",
                        "Eliminates need for dedicated identity management servers",
                        "Stateless role assumption minimizes resource utilization"
                    ]
                }
            ]
        }

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        """Get configuration schema for the UI"""
        return ArchieRoleConfig.get_config_schema()
