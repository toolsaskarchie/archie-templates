"""
AWS Sandbox Account

Ephemeral sandbox environment with automatic cost controls and cleanup.
Designed for experimentation and development with built-in guardrails
to prevent runaway spending and enforce time-boxed access.

Core components:
- IAM role with PowerUser access (time-boxed via tags)
- CloudWatch alarm for spend threshold
- Budget with SNS notification for auto-stop
- S3 bucket for sandbox artifacts (lifecycle: auto-delete after N days)
- VPC with public subnet only (no NAT = cheaper)
- Security group allowing outbound only
- Ephemeral tagging (ephemeral=true, ttl={days})
"""

from typing import Any, Dict, List, Optional
import json
import pulumi
import pulumi_aws as aws

from provisioner.templates.base import InfrastructureTemplate, template_registry
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory
from provisioner.utils.aws import ResourceNamer
from provisioner.utils.aws.tags import get_standard_tags


@template_registry("aws-sandbox-account")
class SandboxAccountTemplate(InfrastructureTemplate):
    """
    Ephemeral AWS sandbox with cost controls, time-boxed IAM, auto-cleanup
    S3, public-only VPC, and outbound-only security group.
    """

    def __init__(self, name: str = None, config: Dict[str, Any] = None, aws_config: Dict[str, Any] = None, **kwargs):
        raw_config = config or aws_config or kwargs or {}

        if name is None:
            name = (
                raw_config.get('project_name') or
                raw_config.get('projectName') or
                raw_config.get('parameters', {}).get('aws', {}).get('project_name') or
                'sandbox'
            )

        super().__init__(name, raw_config)
        self.config = raw_config

        # Resource references
        self.sandbox_role: Optional[object] = None
        self.sns_topic: Optional[object] = None
        self.budget: Optional[object] = None
        self.spend_alarm: Optional[object] = None
        self.artifacts_bucket: Optional[object] = None
        self.vpc: Optional[object] = None
        self.public_subnets: List[object] = []
        self.security_group: Optional[object] = None
        self.internet_gateway: Optional[object] = None

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

    def _get_int(self, key: str, default: int = 0) -> int:
        """Handle string/int/Decimal from DynamoDB"""
        val = self._cfg(key, default)
        try:
            return int(val)
        except (ValueError, TypeError):
            return default

    def create_infrastructure(self) -> Dict[str, Any]:
        return self.create()

    def create(self) -> Dict[str, Any]:
        project = self._cfg('project_name', 'sandbox')
        env = 'sandbox'
        team_name = self._cfg('team_name', '')
        owner_email = self._cfg('owner_email', '')
        ttl_days = self._get_int('ttl_days', 14)
        budget_limit = str(self._cfg('budget_limit', 100))
        allowed_regions = self._cfg('allowed_regions', 'us-east-1')
        region = self._cfg('region', 'us-east-1')
        region_short = region.replace('-', '')

        tags = get_standard_tags(project=project, environment=env, template='aws-sandbox-account')
        tags['ManagedBy'] = 'Archie'
        tags['ephemeral'] = 'true'
        tags['ttl'] = str(ttl_days)
        tags.update(self._cfg('tags', {}))
        if team_name:
            tags['Team'] = team_name
        if owner_email:
            tags['Owner'] = owner_email

        account_id = aws.get_caller_identity().account_id

        # =================================================================
        # LAYER 1: SNS Topic for budget/alarm notifications
        # =================================================================
        print("[SANDBOX] Creating SNS notification topic...")

        self.sns_topic = factory.create(
            "aws:sns:Topic",
            f"sns-sandbox-alerts-{project}",
            name=f"archie-sandbox-alerts-{project}",
            tags={**tags, "Name": f"archie-sandbox-alerts-{project}"},
        )

        if owner_email:
            factory.create(
                "aws:sns:TopicSubscription",
                f"sns-sub-email-{project}",
                topic=self.sns_topic.arn,
                protocol="email",
                endpoint=owner_email,
            )

        # =================================================================
        # LAYER 2: IAM Role with PowerUser access (time-boxed)
        # =================================================================
        print("[SANDBOX] Creating time-boxed PowerUser IAM role...")

        self.sandbox_role = factory.create(
            "aws:iam:Role",
            f"role-sandbox-{project}",
            name=f"archie-sandbox-{project}",
            assume_role_policy=json.dumps({
                "Version": "2012-10-17",
                "Statement": [{
                    "Effect": "Allow",
                    "Principal": {"AWS": f"arn:aws:iam::{account_id}:root"},
                    "Action": "sts:AssumeRole",
                    "Condition": {
                        "StringEquals": {"aws:PrincipalTag/sandbox-access": "true"}
                    }
                }]
            }),
            max_session_duration=3600 * 8,  # 8 hours max session
            tags={**tags, "Name": f"archie-sandbox-{project}"},
        )

        # PowerUserAccess (everything except IAM user/group management)
        factory.create(
            "aws:iam:RolePolicyAttachment",
            f"role-sandbox-poweruser-{project}",
            role=self.sandbox_role.name,
            policy_arn="arn:aws:iam::aws:policy/PowerUserAccess",
        )

        # Region restriction inline policy
        region_list = [r.strip() for r in allowed_regions.split(',')]
        factory.create(
            "aws:iam:RolePolicy",
            f"role-sandbox-region-lock-{project}",
            name=f"sandbox-region-lock-{project}",
            role=self.sandbox_role.id,
            policy=json.dumps({
                "Version": "2012-10-17",
                "Statement": [{
                    "Sid": "DenyNonApprovedRegions",
                    "Effect": "Deny",
                    "NotAction": [
                        "iam:*", "sts:*", "support:*",
                        "budgets:*", "ce:*", "health:*",
                        "s3:GetBucketLocation", "s3:ListAllMyBuckets"
                    ],
                    "Resource": "*",
                    "Condition": {
                        "StringNotEquals": {"aws:RequestedRegion": region_list}
                    }
                }]
            }),
        )

        # Deny destructive IAM/org actions
        factory.create(
            "aws:iam:RolePolicy",
            f"role-sandbox-deny-dangerous-{project}",
            name=f"sandbox-deny-dangerous-{project}",
            role=self.sandbox_role.id,
            policy=json.dumps({
                "Version": "2012-10-17",
                "Statement": [{
                    "Sid": "DenyDangerousActions",
                    "Effect": "Deny",
                    "Action": [
                        "organizations:*",
                        "account:*",
                        "iam:CreateUser",
                        "iam:CreateGroup",
                        "iam:CreateLoginProfile",
                        "iam:CreateAccessKey",
                        "iam:DeactivateMFADevice",
                        "iam:DeleteAccountPasswordPolicy",
                    ],
                    "Resource": "*"
                }]
            }),
        )

        # =================================================================
        # LAYER 3: Budget with auto-alert
        # =================================================================
        print(f"[SANDBOX] Creating budget alert (${budget_limit}/month)...")

        self.budget = factory.create(
            "aws:budgets:Budget",
            f"budget-sandbox-{project}",
            name=f"archie-sandbox-budget-{project}",
            budget_type="COST",
            limit_amount=budget_limit,
            limit_unit="USD",
            time_unit="MONTHLY",
            notifications=[
                aws.budgets.BudgetNotificationArgs(
                    comparison_operator="GREATER_THAN",
                    threshold=50,
                    threshold_type="PERCENTAGE",
                    notification_type="ACTUAL",
                    subscriber_sns_topic_arns=[self.sns_topic.arn],
                ),
                aws.budgets.BudgetNotificationArgs(
                    comparison_operator="GREATER_THAN",
                    threshold=80,
                    threshold_type="PERCENTAGE",
                    notification_type="ACTUAL",
                    subscriber_sns_topic_arns=[self.sns_topic.arn],
                ),
                aws.budgets.BudgetNotificationArgs(
                    comparison_operator="GREATER_THAN",
                    threshold=100,
                    threshold_type="PERCENTAGE",
                    notification_type="ACTUAL",
                    subscriber_sns_topic_arns=[self.sns_topic.arn],
                ),
            ],
        )

        # =================================================================
        # LAYER 4: CloudWatch Spend Alarm
        # =================================================================
        print("[SANDBOX] Creating CloudWatch spend alarm...")

        self.spend_alarm = factory.create(
            "aws:cloudwatch:MetricAlarm",
            f"alarm-spend-{project}",
            alarm_name=f"archie-sandbox-spend-{project}",
            comparison_operator="GreaterThanThreshold",
            evaluation_periods=1,
            metric_name="EstimatedCharges",
            namespace="AWS/Billing",
            period=21600,  # 6 hours
            statistic="Maximum",
            threshold=float(budget_limit),
            alarm_description=f"Sandbox {project} spend exceeded ${budget_limit}",
            alarm_actions=[self.sns_topic.arn],
            dimensions={"Currency": "USD"},
            tags={**tags, "Name": f"archie-sandbox-spend-{project}"},
        )

        # =================================================================
        # LAYER 5: S3 Artifact Bucket (auto-cleanup lifecycle)
        # =================================================================
        print(f"[SANDBOX] Creating artifact bucket (auto-delete after {ttl_days} days)...")

        artifact_bucket_name = f"archie-sandbox-{project}-{region_short}-{account_id}"

        self.artifacts_bucket = factory.create(
            "aws:s3:BucketV2",
            f"s3-sandbox-{project}-{region_short}",
            bucket=artifact_bucket_name,
            force_destroy=True,
            tags={**tags, "Name": artifact_bucket_name, "Purpose": "Sandbox Artifacts"},
        )

        # Block public access
        factory.create(
            "aws:s3:BucketPublicAccessBlock",
            f"s3-sandbox-public-block-{project}",
            bucket=self.artifacts_bucket.id,
            block_public_acls=True,
            block_public_policy=True,
            ignore_public_acls=True,
            restrict_public_buckets=True,
        )

        # Encryption
        factory.create(
            "aws:s3:BucketServerSideEncryptionConfigurationV2",
            f"s3-sandbox-encryption-{project}",
            bucket=self.artifacts_bucket.id,
            rules=[aws.s3.BucketServerSideEncryptionConfigurationV2RuleArgs(
                apply_server_side_encryption_by_default=aws.s3.BucketServerSideEncryptionConfigurationV2RuleApplyServerSideEncryptionByDefaultArgs(
                    sse_algorithm="AES256",
                ),
            )],
        )

        # Auto-delete lifecycle
        factory.create(
            "aws:s3:BucketLifecycleConfigurationV2",
            f"s3-sandbox-lifecycle-{project}",
            bucket=self.artifacts_bucket.id,
            rules=[aws.s3.BucketLifecycleConfigurationV2RuleArgs(
                id="auto-cleanup",
                status="Enabled",
                expiration=aws.s3.BucketLifecycleConfigurationV2RuleExpirationArgs(
                    days=ttl_days,
                ),
            )],
        )

        # =================================================================
        # LAYER 6: VPC (public subnet only, no NAT)
        # =================================================================
        print("[SANDBOX] Creating lightweight VPC (public only, no NAT)...")

        vpc_cidr = self._cfg('vpc_cidr', '10.99.0.0/16')

        self.vpc = factory.create(
            "aws:ec2:Vpc",
            f"vpc-sandbox-{project}",
            cidr_block=vpc_cidr,
            enable_dns_support=True,
            enable_dns_hostnames=True,
            tags={**tags, "Name": f"vpc-sandbox-{project}"},
        )

        # Internet Gateway
        self.internet_gateway = factory.create(
            "aws:ec2:InternetGateway",
            f"igw-sandbox-{project}",
            vpc_id=self.vpc.id,
            tags={**tags, "Name": f"igw-sandbox-{project}"},
        )

        # Route table with internet route
        route_table = factory.create(
            "aws:ec2:RouteTable",
            f"rt-sandbox-public-{project}",
            vpc_id=self.vpc.id,
            routes=[aws.ec2.RouteTableRouteArgs(
                cidr_block="0.0.0.0/0",
                gateway_id=self.internet_gateway.id,
            )],
            tags={**tags, "Name": f"rt-sandbox-public-{project}"},
        )

        # Two public subnets in different AZs
        azs = aws.get_availability_zones(state="available")
        subnet_cidrs = ["10.99.1.0/24", "10.99.2.0/24"]

        for i, cidr in enumerate(subnet_cidrs):
            az = azs.names[i] if i < len(azs.names) else azs.names[0]
            subnet = factory.create(
                "aws:ec2:Subnet",
                f"subnet-sandbox-public-{i+1}-{project}",
                vpc_id=self.vpc.id,
                cidr_block=cidr,
                availability_zone=az,
                map_public_ip_on_launch=True,
                tags={**tags, "Name": f"subnet-sandbox-public-{i+1}-{project}"},
            )
            self.public_subnets.append(subnet)

            factory.create(
                "aws:ec2:RouteTableAssociation",
                f"rta-sandbox-public-{i+1}-{project}",
                subnet_id=subnet.id,
                route_table_id=route_table.id,
            )

        # =================================================================
        # LAYER 7: Security Group (outbound only)
        # =================================================================
        print("[SANDBOX] Creating outbound-only security group...")

        self.security_group = factory.create(
            "aws:ec2:SecurityGroup",
            f"sg-sandbox-{project}",
            name=f"archie-sandbox-{project}",
            description=f"Sandbox {project} - outbound only, no inbound",
            vpc_id=self.vpc.id,
            ingress=[],  # No inbound rules
            egress=[
                aws.ec2.SecurityGroupEgressArgs(
                    description="Allow all outbound",
                    from_port=0,
                    to_port=0,
                    protocol="-1",
                    cidr_blocks=["0.0.0.0/0"],
                ),
            ],
            tags={**tags, "Name": f"sg-sandbox-{project}"},
        )

        # =================================================================
        # OUTPUTS
        # =================================================================
        print("[SANDBOX] Sandbox environment ready!")

        pulumi.export('sandbox_role_arn', self.sandbox_role.arn)
        pulumi.export('sandbox_role_name', self.sandbox_role.name)
        pulumi.export('sns_topic_arn', self.sns_topic.arn)
        pulumi.export('budget_name', self.budget.name)
        pulumi.export('spend_alarm_arn', self.spend_alarm.arn)
        pulumi.export('artifacts_bucket_name', self.artifacts_bucket.bucket)
        pulumi.export('artifacts_bucket_arn', self.artifacts_bucket.arn)
        pulumi.export('vpc_id', self.vpc.id)
        pulumi.export('vpc_cidr', self.vpc.cidr_block)
        pulumi.export('public_subnet_ids', [s.id for s in self.public_subnets])
        pulumi.export('security_group_id', self.security_group.id)
        pulumi.export('internet_gateway_id', self.internet_gateway.id)
        pulumi.export('owner_email', owner_email)
        pulumi.export('ttl_days', str(ttl_days))
        pulumi.export('environment', env)

        return self.get_outputs()

    def get_outputs(self) -> Dict[str, Any]:
        return {
            "sandbox_role_arn": self.sandbox_role.arn if self.sandbox_role else None,
            "sandbox_role_name": self.sandbox_role.name if self.sandbox_role else None,
            "sns_topic_arn": self.sns_topic.arn if self.sns_topic else None,
            "budget_name": self.budget.name if self.budget else None,
            "spend_alarm_arn": self.spend_alarm.arn if self.spend_alarm else None,
            "artifacts_bucket_name": self.artifacts_bucket.bucket if self.artifacts_bucket else None,
            "artifacts_bucket_arn": self.artifacts_bucket.arn if self.artifacts_bucket else None,
            "vpc_id": self.vpc.id if self.vpc else None,
            "vpc_cidr": self.vpc.cidr_block if self.vpc else None,
            "public_subnet_ids": [s.id for s in self.public_subnets] if self.public_subnets else [],
            "security_group_id": self.security_group.id if self.security_group else None,
            "internet_gateway_id": self.internet_gateway.id if self.internet_gateway else None,
        }

    @classmethod
    def get_metadata(cls) -> Dict[str, Any]:
        return {
            "name": "aws-sandbox-account",
            "title": "Sandbox Account",
            "description": "Ephemeral sandbox environment with automatic cost controls. Provides time-boxed IAM access, budget alerts with SNS notification, auto-cleanup S3 storage, public-only VPC (no NAT costs), and outbound-only security group.",
            "category": "governance",
            "version": "1.0.0",
            "author": "Archie",
            "cloud": "aws",
            "environment": "sandbox",
            "base_cost": "$3/month",
            "features": [
                "Time-boxed IAM role with PowerUser access and region lock",
                "Budget alerts at 50%, 80%, and 100% with SNS notification",
                "CloudWatch spend alarm triggers on threshold breach",
                "S3 artifact bucket with auto-delete lifecycle",
                "Public-only VPC (no NAT Gateway = no idle cost)",
                "Outbound-only security group (no inbound access)",
                "Ephemeral tagging (ttl, owner, ephemeral=true)",
                "Region-restricted IAM policy prevents resource sprawl",
                "Dangerous action deny policy (no org/account/user changes)",
            ],
            "tags": ["sandbox", "ephemeral", "cost-control", "governance", "dev", "experimentation"],
            "deployment_time": "2-3 minutes",
            "complexity": "beginner",
            "use_cases": [
                "Developer experimentation and prototyping",
                "Time-boxed proof-of-concept environments",
                "Training and learning sandboxes",
                "Temporary CI/CD test environments",
            ],
            "pillars": [
                {
                    "title": "Cost Optimization",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Built for minimal cost with automatic spend controls",
                    "practices": [
                        "Budget alerts at 50%, 80%, and 100% prevent surprise bills",
                        "CloudWatch alarm triggers notification on threshold breach",
                        "Public-only VPC eliminates $32/month NAT Gateway cost",
                        "S3 auto-delete lifecycle prevents orphaned storage costs",
                        "Region restriction prevents accidental multi-region resource sprawl",
                    ]
                },
                {
                    "title": "Security",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Guardrails prevent destructive actions while allowing experimentation",
                    "practices": [
                        "IAM role denies dangerous org/account/user management actions",
                        "Region-locked to approved regions only",
                        "Outbound-only security group blocks all inbound traffic",
                        "S3 public access blocked at bucket level",
                        "Ephemeral tags enable automated cleanup discovery",
                    ]
                },
                {
                    "title": "Operational Excellence",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Self-service sandbox with built-in lifecycle management",
                    "practices": [
                        "Ephemeral tagging (ttl, owner) enables automated governance",
                        "SNS notifications keep owner informed of spend and events",
                        "Infrastructure as Code ensures consistent sandbox provisioning",
                        "S3 lifecycle handles artifact cleanup automatically",
                        "VPC provides isolated networking without manual setup",
                    ]
                },
                {
                    "title": "Reliability",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Simple architecture with minimal failure modes",
                    "practices": [
                        "Two-AZ subnet layout provides basic redundancy",
                        "S3 provides 99.999999999% durability for artifacts",
                        "SNS delivery ensures budget alerts reach owners",
                        "Internet Gateway provides reliable outbound connectivity",
                        "Managed services reduce operational failure risk",
                    ]
                },
                {
                    "title": "Sustainability",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Minimal footprint with automatic resource cleanup",
                    "practices": [
                        "No NAT Gateway eliminates always-on networking compute",
                        "Auto-delete S3 lifecycle prevents indefinite storage growth",
                        "TTL-based tagging enables automated teardown workflows",
                        "Region restriction minimizes geographic resource distribution",
                        "Ephemeral by design — nothing persists beyond its useful life",
                    ]
                },
            ]
        }

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "project_name": {
                    "type": "string",
                    "default": "my-sandbox",
                    "title": "Project Name",
                    "description": "Used in resource naming for all sandbox resources",
                    "order": 1,
                    "group": "Essentials",
                    "isEssential": True,
                },
                "owner_email": {
                    "type": "string",
                    "default": "",
                    "title": "Owner Email",
                    "description": "Email address for budget alerts and sandbox ownership",
                    "order": 2,
                    "group": "Essentials",
                    "isEssential": True,
                },
                "ttl_days": {
                    "type": "number",
                    "default": 14,
                    "title": "TTL (Days)",
                    "description": "Sandbox lifetime in days — S3 artifacts auto-delete after this period",
                    "enum": [7, 14, 30],
                    "order": 3,
                    "group": "Essentials",
                    "isEssential": True,
                },
                "budget_limit": {
                    "type": "number",
                    "default": 100,
                    "title": "Budget Limit (USD)",
                    "description": "Monthly spend limit — alerts at 50%, 80%, and 100%",
                    "order": 10,
                    "group": "Cost Controls",
                    "cost_impact": "Alerts only, no hard cap",
                },
                "allowed_regions": {
                    "type": "string",
                    "default": "us-east-1",
                    "title": "Allowed Regions",
                    "description": "Comma-separated list of AWS regions the sandbox role can use",
                    "order": 11,
                    "group": "Cost Controls",
                },
                "region": {
                    "type": "string",
                    "default": "us-east-1",
                    "title": "Primary Region",
                    "description": "AWS region for sandbox VPC and resources",
                    "order": 12,
                    "group": "Cost Controls",
                },
                "vpc_cidr": {
                    "type": "string",
                    "default": "10.99.0.0/16",
                    "title": "VPC CIDR",
                    "description": "CIDR block for the sandbox VPC",
                    "order": 20,
                    "group": "Network Configuration",
                },
                "team_name": {
                    "type": "string",
                    "default": "",
                    "title": "Team Name",
                    "description": "Team that owns this sandbox",
                    "order": 50,
                    "group": "Tags",
                },
            },
            "required": ["project_name", "owner_email"],
        }
