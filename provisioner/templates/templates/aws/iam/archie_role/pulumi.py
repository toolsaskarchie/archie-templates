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
    def get_metadata(cls):
        """Template metadata for marketplace registration"""
        from provisioner.templates.base.template import TemplateMetadata, TemplateCategory
        return TemplateMetadata(
            name="aws-archie-role",
            title="Archie Connection Role",
            description="Secure cross-account IAM role that allows Archie to safely discover and manage infrastructure in your AWS account. Uses industry-standard STS External ID and restricted read-only permissions.",
            category=TemplateCategory.SECURITY,
            version="1.0.0",
            author="InnovativeApps",
            tags=["iam", "role", "security", "connection"],
            features=[
                "Secure Cross-Account Trust relationship",
                "Principle of Least Privilege restricted policies",
                "Mandatory External ID verification for security",
                "No long-term credentials required",
                "Automated policy lifecycle management"
            ],
            estimated_cost="$0.00/month",
            complexity="intermediate",
            deployment_time="1-2 minutes",
            marketplace_group="SECURITY"
        )

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        """Get configuration schema for the UI"""
        return ArchieRoleConfig.get_config_schema()

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        """Get configuration schema for the UI"""
        return ArchieRoleConfig.get_config_schema()

    @classmethod
    def get_metadata(cls):
        """Get template metadata"""
        from provisioner.templates.base.template import TemplateMetadata, TemplateCategory
        return TemplateMetadata(
            name="aws-archie-role",
            title="Archie Cross-Account Role",
            description="Secure, managed IAM role for connecting your AWS account to Archie. Implements the principle of least privilege using restricted read-only permissions and STS External ID verification. The industry-standard approach for cross-account infrastructure management.",
            category=TemplateCategory.SECURITY,
            version="1.0.0",
            author="InnovativeApps",
            tags=["iam", "role", "security", "connection", "managed"],
            features=[
                "Secure Cross-Account Trust Policy",
                "Mandatory STS External ID Verification",
                "Restricted Read-Only permissions for discovery",
                "Automated Customer Managed Policy creation",
                "Managed via Pulumi Infrastructure-as-Code",
                "No long-term credentials or access keys required"
            ],
            estimated_cost="$0.00/month (IAM is free)",
            complexity="intermediate",
            deployment_time="1-2 minutes",
            marketplace_group="aws-security-group"
        )
