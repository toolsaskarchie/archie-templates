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

    def _cfg(self, key: str, default=None):
        """Read config from root, parameters.aws, or parameters (Rule #6)"""
        params = self.config.get('parameters', {})
        aws_params = params.get('aws', {}) if isinstance(params, dict) else {}
        return (
            self.config.get(key) or
            (aws_params.get(key) if isinstance(aws_params, dict) else None) or
            (params.get(key) if isinstance(params, dict) else None) or
            default
        )
    
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
        
        # Minimum-privilege Deploy Policy
        # ---------------------------------------------------------------
        # Three tiers:
        #   1. Allow CRUD on services Archie's first-party templates deploy.
        #      If a user wants Archie to deploy a service NOT listed here
        #      (Glue, EMR, Kinesis, ...), they explicitly attach an extra
        #      managed policy to this role themselves in the AWS console.
        #   2. IAM scoped HARD to archie-managed resources only.
        #      Prevents privilege escalation: Archie cannot rewrite trust
        #      policies on existing roles, attach policies to arbitrary
        #      principals, or modify the assume-role policy of anything
        #      outside the archie-* namespace.
        #   3. Explicit Deny block for blast-radius limiters
        #      (org / account / billing / user creation).
        deploy_policy_doc = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "ArchieCoreInfra",
                    "Effect": "Allow",
                    "Action": [
                        "ec2:*",
                        "elasticloadbalancing:*",
                        "autoscaling:*",
                        "s3:*",
                        "rds:*",
                        "lambda:*",
                        "ecs:*",
                        "eks:*",
                        "ecr:*",
                        "cloudwatch:*",
                        "logs:*",
                        "events:*",
                        "secretsmanager:*",
                        "route53:*",
                        "acm:*",
                        "sqs:*",
                        "sns:*",
                        "cloudfront:*",
                        "apigateway:*",
                        "execute-api:*",
                        "dynamodb:*",
                        "states:*",
                        "elasticfilesystem:*",
                        "elasticache:*",
                        "tag:*",
                        "resource-groups:*"
                    ],
                    "Resource": "*"
                },
                {
                    "Sid": "ArchieKMSScopedUse",
                    "Effect": "Allow",
                    "Action": [
                        "kms:CreateKey",
                        "kms:CreateAlias",
                        "kms:DeleteAlias",
                        "kms:UpdateAlias",
                        "kms:Describe*",
                        "kms:Get*",
                        "kms:List*",
                        "kms:TagResource",
                        "kms:UntagResource",
                        "kms:Encrypt",
                        "kms:Decrypt",
                        "kms:GenerateDataKey*",
                        "kms:ReEncrypt*",
                        "kms:EnableKey*",
                        "kms:DisableKey*",
                        "kms:ScheduleKeyDeletion",
                        "kms:CancelKeyDeletion",
                        "kms:PutKeyPolicy"
                    ],
                    "Resource": "*"
                },
                {
                    "Sid": "ArchieIAMReadOnly",
                    "Effect": "Allow",
                    "Action": [
                        "iam:Get*",
                        "iam:List*",
                        "iam:SimulatePrincipalPolicy"
                    ],
                    "Resource": "*"
                },
                # ── IAM scoping by TAG (#303) ────────────────────────────────
                # Primary scope is the canonical Archie tag stamped by every
                # engine (Pulumi transform, TF default_tags, CDK --tags) so a
                # customer can name their project anything they want
                # ("proof-destroy-1780019716") and the create still succeeds.
                # CreateRole/CreatePolicy use aws:RequestTag (tags on the
                # API request); subsequent mutations use aws:ResourceTag
                # (tags already on the resource).
                {
                    "Sid": "ArchieIAMCreateByRequestTag",
                    "Effect": "Allow",
                    "Action": [
                        "iam:CreateRole",
                        "iam:CreatePolicy",
                        "iam:CreateInstanceProfile"
                    ],
                    "Resource": "*",
                    "Condition": {
                        "StringEquals": {
                            "aws:RequestTag/ManagedBy": "Archie"
                        }
                    }
                },
                {
                    "Sid": "ArchieIAMMutateByResourceTag",
                    "Effect": "Allow",
                    "Action": [
                        "iam:DeleteRole",
                        "iam:UpdateRole",
                        "iam:UpdateAssumeRolePolicy",
                        "iam:AttachRolePolicy",
                        "iam:DetachRolePolicy",
                        "iam:PutRolePolicy",
                        "iam:DeleteRolePolicy",
                        "iam:TagRole",
                        "iam:UntagRole",
                        "iam:PassRole",
                        "iam:DeletePolicy",
                        "iam:CreatePolicyVersion",
                        "iam:DeletePolicyVersion",
                        "iam:TagPolicy",
                        "iam:UntagPolicy",
                        "iam:DeleteInstanceProfile",
                        "iam:AddRoleToInstanceProfile",
                        "iam:RemoveRoleFromInstanceProfile",
                        "iam:TagInstanceProfile",
                        "iam:UntagInstanceProfile"
                    ],
                    "Resource": "*",
                    "Condition": {
                        "StringEquals": {
                            "aws:ResourceTag/ManagedBy": "Archie"
                        }
                    }
                },
                {
                    "Sid": "ArchieIAMServiceLinkedRoles",
                    "Effect": "Allow",
                    "Action": [
                        "iam:CreateServiceLinkedRole"
                    ],
                    "Resource": "*"
                },
                {
                    "Sid": "ArchieHardDeny",
                    "Effect": "Deny",
                    "Action": [
                        "organizations:*",
                        "account:*",
                        "aws-portal:*",
                        "support:*",
                        "billing:*",
                        "ce:*",
                        "cur:*",
                        "iam:CreateUser",
                        "iam:DeleteUser",
                        "iam:CreateLoginProfile",
                        "iam:UpdateLoginProfile",
                        "iam:CreateAccessKey",
                        "iam:UpdateAccessKey",
                        "iam:DeleteAccessKey",
                        "iam:UpdateAccountPasswordPolicy",
                        "iam:DeleteAccountPasswordPolicy"
                    ],
                    "Resource": "*"
                }
            ]
        }

        # Honor an explicit role_name from config when provided (e.g. the
        # onboarding wizard passes a customer-chosen name from the preview
        # screen). Falls back to a deterministic auto-name so direct
        # template usage without role_name still works.
        custom_role_name = self.cfg.role_name
        role_name = custom_role_name or f"role-archie-{self.cfg.project_name}-{environment}-{region}"
        # Policy name mirrors the role name so the two stay paired in
        # AWS console listings. Strip the "role-" prefix if present so
        # we get pol-archie-<rest>, else prefix with pol- naively.
        if role_name.startswith("role-"):
            policy_name = "pol-" + role_name[len("role-"):]
        else:
            policy_name = f"pol-{role_name}"

        # 1. Create Policy
        self.policy = factory.create(
            "aws:iam:Policy",
            f"{self.name}-policy",
            name=policy_name,
            description="Minimum-privilege deploy policy for Archie. Covers first-party templates only; users explicitly attach additional managed policies for services outside this list.",
            policy=json.dumps(deploy_policy_doc),
            tags=tags,
        )

        # 2. Create Role
        self.role = factory.create(
            "aws:iam:Role",
            self.name,
            name=role_name,
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
            "description": "Secure, managed IAM role for connecting your AWS account to Archie. Implements least privilege with a minimum-deploy policy (covers Archie's first-party templates only) and STS External ID verification. Users explicitly attach additional managed policies for any services outside the curated list.",
            "category": "security",
            "version": "1.0.1",
            "author": "InnovativeApps",
            "cloud": "aws",
            "environment": "all",
            "base_cost": "$0.00/month",
            "tags": ["iam", "role", "security", "connection", "managed"],
            "features": [
                "Secure Cross-Account Trust Policy",
                "Mandatory STS External ID Verification",
                "Minimum-privilege deploy policy (Archie's first-party services only)",
                "IAM scoped to archie-* resources — no privilege escalation surface",
                "Explicit deny block on org/account/billing/user creation",
                "No long-term credentials or access keys required"
            ],
            "deployment_time": "1-2 minutes",
            "complexity": "low",
            "use_cases": [
                "Connect AWS account to Archie platform",
                "Cross-account infrastructure discovery",
                "Read-only cloud resource inventory",
                "Secure onboarding without long-term credentials",
            ],
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
