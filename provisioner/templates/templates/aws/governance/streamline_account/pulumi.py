"""
AWS Streamlined Account Setup

Essential governance baseline for a new AWS account — not a full landing zone,
just the security and compliance essentials every account needs from day one.

Core components:
- CloudTrail (organization trail, S3 bucket, KMS encryption)
- AWS Config (recorder, delivery channel, S3 bucket)
- GuardDuty detector
- SecurityHub (CIS + AWS Foundational benchmarks)
- IAM password policy
- S3 block public access (account-level)
- EBS default encryption
- Budget alert (configurable threshold)
- Default VPC deletion (optional)
"""

from typing import Any, Dict, Optional
import json
import pulumi
import pulumi_aws as aws

from provisioner.templates.base import InfrastructureTemplate, template_registry
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory
from provisioner.utils.aws import ResourceNamer
from provisioner.utils.aws.tags import get_standard_tags


@template_registry("aws-streamline-account")
class StreamlineAccountTemplate(InfrastructureTemplate):
    """
    Streamlined AWS account governance baseline — CloudTrail, Config,
    GuardDuty, SecurityHub, password policy, encryption defaults, budget.
    """

    def __init__(self, name: str = None, config: Dict[str, Any] = None, aws_config: Dict[str, Any] = None, **kwargs):
        raw_config = config or aws_config or kwargs or {}

        if name is None:
            name = (
                raw_config.get('project_name') or
                raw_config.get('projectName') or
                raw_config.get('parameters', {}).get('aws', {}).get('project_name') or
                'streamline-account'
            )

        super().__init__(name, raw_config)
        self.config = raw_config

        # Resource references
        self.kms_key: Optional[object] = None
        self.trail_bucket: Optional[object] = None
        self.trail: Optional[object] = None
        self.config_bucket: Optional[object] = None
        self.config_recorder: Optional[object] = None
        self.guardduty_detector: Optional[object] = None
        self.securityhub: Optional[object] = None
        self.password_policy: Optional[object] = None
        self.account_public_access_block: Optional[object] = None
        self.ebs_encryption: Optional[object] = None
        self.budget: Optional[object] = None

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

    def _get_bool(self, key: str, default: bool = False) -> bool:
        """Handle string/bool/Decimal from DynamoDB"""
        val = self._cfg(key, default)
        if isinstance(val, str):
            return val.lower() in ('true', '1', 'yes')
        return bool(val)

    def create_infrastructure(self) -> Dict[str, Any]:
        return self.create()

    def create(self) -> Dict[str, Any]:
        project = self._cfg('project_name', 'streamline')
        env = self._cfg('environment', 'foundation')
        team_name = self._cfg('team_name', '')
        region = self._cfg('region', 'us-east-1')
        region_short = region.replace('-', '')

        tags = get_standard_tags(project=project, environment=env, template='aws-streamline-account')
        tags['ManagedBy'] = 'Archie'
        tags.update(self._cfg('tags', {}))
        if team_name:
            tags['Team'] = team_name

        account_id = aws.get_caller_identity().account_id

        # =================================================================
        # LAYER 1: KMS Key for CloudTrail encryption
        # =================================================================
        print("[STREAMLINE] Creating KMS key for CloudTrail encryption...")

        self.kms_key = factory.create(
            "aws:kms:Key",
            f"kms-cloudtrail-{project}-{env}",
            description=f"KMS key for CloudTrail encryption - {project}",
            enable_key_rotation=True,
            policy=json.dumps({
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Sid": "EnableRootAccountAccess",
                        "Effect": "Allow",
                        "Principal": {"AWS": f"arn:aws:iam::{account_id}:root"},
                        "Action": "kms:*",
                        "Resource": "*"
                    },
                    {
                        "Sid": "AllowCloudTrailEncrypt",
                        "Effect": "Allow",
                        "Principal": {"Service": "cloudtrail.amazonaws.com"},
                        "Action": [
                            "kms:GenerateDataKey*",
                            "kms:DescribeKey"
                        ],
                        "Resource": "*",
                        "Condition": {
                            "StringEquals": {"aws:SourceArn": f"arn:aws:cloudtrail:{region}:{account_id}:trail/archie-trail-{project}-{region_short}"},
                            "StringLike": {"kms:EncryptionContext:aws:cloudtrail:arn": f"arn:aws:cloudtrail:*:{account_id}:trail/*"}
                        }
                    }
                ]
            }),
            tags={**tags, "Name": f"kms-cloudtrail-{project}-{env}"},
        )

        factory.create(
            "aws:kms:Alias",
            f"kms-alias-cloudtrail-{project}-{env}",
            name=f"alias/archie-cloudtrail-{project}-{env}",
            target_key_id=self.kms_key.id,
        )

        # =================================================================
        # LAYER 2: CloudTrail S3 Bucket + Trail
        # =================================================================
        print("[STREAMLINE] Creating CloudTrail logging bucket and trail...")

        trail_bucket_name = f"archie-trail-{project}-{region_short}-{account_id}"

        self.trail_bucket = factory.create(
            "aws:s3:BucketV2",
            f"s3-trail-{project}-{region_short}",
            bucket=trail_bucket_name,
            force_destroy=False,
            tags={**tags, "Name": trail_bucket_name, "Purpose": "CloudTrail Logs"},
        )

        # Block public access on trail bucket
        factory.create(
            "aws:s3:BucketPublicAccessBlock",
            f"s3-trail-public-block-{project}",
            bucket=self.trail_bucket.id,
            block_public_acls=True,
            block_public_policy=True,
            ignore_public_acls=True,
            restrict_public_buckets=True,
        )

        # Encryption
        factory.create(
            "aws:s3:BucketServerSideEncryptionConfigurationV2",
            f"s3-trail-encryption-{project}",
            bucket=self.trail_bucket.id,
            rules=[aws.s3.BucketServerSideEncryptionConfigurationV2RuleArgs(
                apply_server_side_encryption_by_default=aws.s3.BucketServerSideEncryptionConfigurationV2RuleApplyServerSideEncryptionByDefaultArgs(
                    sse_algorithm="aws:kms",
                    kms_master_key_id=self.kms_key.arn,
                ),
            )],
        )

        # Versioning
        factory.create(
            "aws:s3:BucketVersioningV2",
            f"s3-trail-versioning-{project}",
            bucket=self.trail_bucket.id,
            versioning_configuration={"status": "Enabled"},
        )

        # Lifecycle — transition to Glacier, then expire
        factory.create(
            "aws:s3:BucketLifecycleConfigurationV2",
            f"s3-trail-lifecycle-{project}",
            bucket=self.trail_bucket.id,
            rules=[aws.s3.BucketLifecycleConfigurationV2RuleArgs(
                id="archive-old-logs",
                status="Enabled",
                transitions=[aws.s3.BucketLifecycleConfigurationV2RuleTransitionArgs(
                    days=90,
                    storage_class="GLACIER",
                )],
                expiration=aws.s3.BucketLifecycleConfigurationV2RuleExpirationArgs(
                    days=365,
                ),
            )],
        )

        # Bucket policy for CloudTrail
        factory.create(
            "aws:s3:BucketPolicy",
            f"s3-trail-policy-{project}",
            bucket=self.trail_bucket.id,
            policy=self.trail_bucket.arn.apply(lambda arn: json.dumps({
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Sid": "AWSCloudTrailAclCheck",
                        "Effect": "Allow",
                        "Principal": {"Service": "cloudtrail.amazonaws.com"},
                        "Action": "s3:GetBucketAcl",
                        "Resource": arn,
                    },
                    {
                        "Sid": "AWSCloudTrailWrite",
                        "Effect": "Allow",
                        "Principal": {"Service": "cloudtrail.amazonaws.com"},
                        "Action": "s3:PutObject",
                        "Resource": f"{arn}/AWSLogs/{account_id}/*",
                        "Condition": {"StringEquals": {"s3:x-amz-acl": "bucket-owner-full-control"}},
                    },
                ]
            })),
        )

        # CloudTrail
        trail_name = f"archie-trail-{project}-{region_short}"
        self.trail = factory.create(
            "aws:cloudtrail:Trail",
            f"trail-{project}-{region_short}",
            name=trail_name,
            is_multi_region_trail=True,
            enable_log_file_validation=True,
            s3_bucket_name=self.trail_bucket.bucket,
            kms_key_id=self.kms_key.arn,
            include_global_service_events=True,
            tags={**tags, "Name": trail_name},
            opts=pulumi.ResourceOptions(depends_on=[self.trail_bucket]),
        )

        # =================================================================
        # LAYER 3: AWS Config (recorder + delivery channel)
        # =================================================================
        enable_config = self._get_bool('enable_config', True)
        if enable_config:
            print("[STREAMLINE] Creating AWS Config recorder...")

            config_bucket_name = f"archie-config-{project}-{region_short}-{account_id}"

            self.config_bucket = factory.create(
                "aws:s3:BucketV2",
                f"s3-config-{project}-{region_short}",
                bucket=config_bucket_name,
                force_destroy=False,
                tags={**tags, "Name": config_bucket_name, "Purpose": "AWS Config Delivery"},
            )

            factory.create(
                "aws:s3:BucketPublicAccessBlock",
                f"s3-config-public-block-{project}",
                bucket=self.config_bucket.id,
                block_public_acls=True,
                block_public_policy=True,
                ignore_public_acls=True,
                restrict_public_buckets=True,
            )

            factory.create(
                "aws:s3:BucketServerSideEncryptionConfigurationV2",
                f"s3-config-encryption-{project}",
                bucket=self.config_bucket.id,
                rules=[aws.s3.BucketServerSideEncryptionConfigurationV2RuleArgs(
                    apply_server_side_encryption_by_default=aws.s3.BucketServerSideEncryptionConfigurationV2RuleApplyServerSideEncryptionByDefaultArgs(
                        sse_algorithm="aws:kms",
                    ),
                )],
            )

            # Config IAM role
            config_role = factory.create(
                "aws:iam:Role",
                f"role-config-{project}",
                name=f"archie-config-recorder-{project}",
                assume_role_policy=json.dumps({
                    "Version": "2012-10-17",
                    "Statement": [{
                        "Effect": "Allow",
                        "Principal": {"Service": "config.amazonaws.com"},
                        "Action": "sts:AssumeRole"
                    }]
                }),
                tags=tags,
            )

            factory.create(
                "aws:iam:RolePolicyAttachment",
                f"role-config-policy-{project}",
                role=config_role.name,
                policy_arn="arn:aws:iam::aws:policy/service-role/AWS_ConfigRole",
            )

            # Config recorder
            self.config_recorder = factory.create(
                "aws:cfg:Recorder",
                f"config-recorder-{project}",
                name=f"archie-recorder-{project}",
                role_arn=config_role.arn,
                recording_group=aws.cfg.RecorderRecordingGroupArgs(
                    all_supported=True,
                    include_global_resource_types=True,
                ),
            )

            # Delivery channel
            factory.create(
                "aws:cfg:DeliveryChannel",
                f"config-delivery-{project}",
                name=f"archie-delivery-{project}",
                s3_bucket_name=self.config_bucket.bucket,
                snapshot_delivery_properties=aws.cfg.DeliveryChannelSnapshotDeliveryPropertiesArgs(
                    delivery_frequency="TwentyFour_Hours",
                ),
                opts=pulumi.ResourceOptions(depends_on=[self.config_recorder]),
            )

            # Start recorder
            factory.create(
                "aws:cfg:RecorderStatus",
                f"config-recorder-status-{project}",
                name=self.config_recorder.name,
                is_enabled=True,
                opts=pulumi.ResourceOptions(depends_on=[self.config_recorder]),
            )

        # =================================================================
        # LAYER 4: GuardDuty
        # =================================================================
        enable_guardduty = self._get_bool('enable_guardduty', True)
        guardduty_detector_id = None
        if enable_guardduty:
            print("[STREAMLINE] Enabling GuardDuty detector...")

            self.guardduty_detector = factory.create(
                "aws:guardduty:Detector",
                f"guardduty-{project}",
                enable=True,
                finding_publishing_frequency="FIFTEEN_MINUTES",
                datasources=aws.guardduty.DetectorDatasourcesArgs(
                    s3_logs=aws.guardduty.DetectorDatasourcesS3LogsArgs(enable=True),
                    malware_protection=aws.guardduty.DetectorDatasourcesMalwareProtectionArgs(
                        scan_ec2_instance_with_findings=aws.guardduty.DetectorDatasourcesMalwareProtectionScanEc2InstanceWithFindingsArgs(
                            ebs_volumes=aws.guardduty.DetectorDatasourcesMalwareProtectionScanEc2InstanceWithFindingsEbsVolumesArgs(enable=True),
                        ),
                    ),
                ),
            )
            guardduty_detector_id = self.guardduty_detector.id

        # =================================================================
        # LAYER 5: SecurityHub
        # =================================================================
        enable_securityhub = self._get_bool('enable_securityhub', True)
        securityhub_arn = None
        if enable_securityhub:
            print("[STREAMLINE] Enabling SecurityHub with CIS + Foundational benchmarks...")

            self.securityhub = factory.create(
                "aws:securityhub:Account",
                f"securityhub-{project}",
            )

            # CIS Benchmark
            factory.create(
                "aws:securityhub:StandardsSubscription",
                f"securityhub-cis-{project}",
                standards_arn="arn:aws:securityhub:::ruleset/cis-aws-foundations-benchmark/v/1.4.0",
                opts=pulumi.ResourceOptions(depends_on=[self.securityhub]),
            )

            # AWS Foundational Best Practices
            factory.create(
                "aws:securityhub:StandardsSubscription",
                f"securityhub-foundational-{project}",
                standards_arn="arn:aws:securityhub:::standards/aws-foundational-security-best-practices/v/1.0.0",
                opts=pulumi.ResourceOptions(depends_on=[self.securityhub]),
            )

            securityhub_arn = self.securityhub.arn

        # =================================================================
        # LAYER 6: IAM Password Policy
        # =================================================================
        print("[STREAMLINE] Setting IAM account password policy...")

        self.password_policy = factory.create(
            "aws:iam:AccountPasswordPolicy",
            f"password-policy-{project}",
            minimum_password_length=14,
            require_symbols=True,
            require_numbers=True,
            require_uppercase_characters=True,
            require_lowercase_characters=True,
            allow_users_to_change_password=True,
            max_password_age=90,
            password_reuse_prevention=24,
        )

        # =================================================================
        # LAYER 7: S3 Account-Level Public Access Block
        # =================================================================
        print("[STREAMLINE] Blocking public access at account level...")

        self.account_public_access_block = factory.create(
            "aws:s3:AccountPublicAccessBlock",
            f"account-public-access-block-{project}",
            block_public_acls=True,
            block_public_policy=True,
            ignore_public_acls=True,
            restrict_public_buckets=True,
        )

        # =================================================================
        # LAYER 8: EBS Default Encryption
        # =================================================================
        print("[STREAMLINE] Enabling EBS default encryption...")

        self.ebs_encryption = factory.create(
            "aws:ec2:EbsDefaultKmsKey",
            f"ebs-default-kms-{project}",
            key_arn=self.kms_key.arn,
        )

        factory.create(
            "aws:ec2:EbsEncryptionByDefault",
            f"ebs-encryption-default-{project}",
            enabled=True,
        )

        # =================================================================
        # LAYER 9: Budget Alert
        # =================================================================
        budget_amount = str(self._cfg('budget_amount', 1000))
        budget_email = self._cfg('budget_email', '')

        print(f"[STREAMLINE] Creating budget alert (${budget_amount}/month)...")

        notifications = [
            aws.budgets.BudgetNotificationArgs(
                comparison_operator="GREATER_THAN",
                threshold=80,
                threshold_type="PERCENTAGE",
                notification_type="ACTUAL",
                subscriber_email_addresses=[budget_email] if budget_email else [],
            ),
            aws.budgets.BudgetNotificationArgs(
                comparison_operator="GREATER_THAN",
                threshold=100,
                threshold_type="PERCENTAGE",
                notification_type="ACTUAL",
                subscriber_email_addresses=[budget_email] if budget_email else [],
            ),
        ]

        self.budget = factory.create(
            "aws:budgets:Budget",
            f"budget-{project}",
            name=f"archie-budget-{project}",
            budget_type="COST",
            limit_amount=budget_amount,
            limit_unit="USD",
            time_unit="MONTHLY",
            notifications=notifications,
        )

        # =================================================================
        # LAYER 10: Delete Default VPC (Optional)
        # =================================================================
        delete_default_vpc = self._get_bool('delete_default_vpc', False)
        if delete_default_vpc:
            print("[STREAMLINE] Deleting default VPC...")

            factory.create(
                "aws:ec2:DefaultVpc",
                f"default-vpc-{project}",
                force_destroy=True,
                tags={**tags, "Name": "default-vpc-marked-for-deletion"},
            )

        # =================================================================
        # OUTPUTS
        # =================================================================
        print("[STREAMLINE] Account governance baseline complete!")

        pulumi.export('kms_key_arn', self.kms_key.arn)
        pulumi.export('kms_key_id', self.kms_key.id)
        pulumi.export('trail_bucket_name', self.trail_bucket.bucket)
        pulumi.export('trail_bucket_arn', self.trail_bucket.arn)
        pulumi.export('trail_name', self.trail.name)
        pulumi.export('trail_arn', self.trail.arn)
        pulumi.export('environment', env)

        if self.config_bucket:
            pulumi.export('config_bucket_name', self.config_bucket.bucket)
            pulumi.export('config_recorder_name', self.config_recorder.name if self.config_recorder else None)
        if guardduty_detector_id:
            pulumi.export('guardduty_detector_id', guardduty_detector_id)
        if securityhub_arn:
            pulumi.export('securityhub_arn', securityhub_arn)
        pulumi.export('budget_name', self.budget.name)

        return self.get_outputs()

    def get_outputs(self) -> Dict[str, Any]:
        return {
            "kms_key_arn": self.kms_key.arn if self.kms_key else None,
            "kms_key_id": self.kms_key.id if self.kms_key else None,
            "trail_bucket_name": self.trail_bucket.bucket if self.trail_bucket else None,
            "trail_bucket_arn": self.trail_bucket.arn if self.trail_bucket else None,
            "trail_name": self.trail.name if self.trail else None,
            "trail_arn": self.trail.arn if self.trail else None,
            "config_bucket_name": self.config_bucket.bucket if self.config_bucket else None,
            "config_recorder_name": self.config_recorder.name if self.config_recorder else None,
            "guardduty_detector_id": self.guardduty_detector.id if self.guardduty_detector else None,
            "securityhub_arn": self.securityhub.arn if self.securityhub else None,
            "budget_name": self.budget.name if self.budget else None,
        }

    @classmethod
    def get_metadata(cls) -> Dict[str, Any]:
        return {
            "name": "aws-streamline-account",
            "title": "Streamlined Account Setup",
            "description": "Essential governance baseline for a new AWS account. Deploys CloudTrail with KMS encryption, AWS Config recorder, GuardDuty, SecurityHub, IAM password policy, account-level S3 public access block, EBS default encryption, and budget alerts.",
            "category": "governance",
            "version": "1.0.0",
            "author": "Archie",
            "cloud": "aws",
            "environment": "foundation",
            "base_cost": "$5/month",
            "features": [
                "CloudTrail with KMS encryption and S3 logging",
                "AWS Config recorder with delivery to S3",
                "GuardDuty threat detection with S3 and malware scanning",
                "SecurityHub with CIS and AWS Foundational benchmarks",
                "IAM password policy (14-char, rotation, reuse prevention)",
                "Account-level S3 public access block",
                "EBS default encryption via KMS",
                "Budget alerts at 80% and 100% thresholds",
                "Optional default VPC deletion",
            ],
            "tags": ["governance", "security", "compliance", "account-setup", "cloudtrail", "guardduty", "config"],
            "deployment_time": "3-5 minutes",
            "complexity": "intermediate",
            "use_cases": [
                "New AWS account governance baseline",
                "Security compliance bootstrapping",
                "CIS Benchmark alignment",
                "Cost control for new accounts",
            ],
            "pillars": [
                {
                    "title": "Security",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Defense-in-depth with encryption, threat detection, and hardened IAM",
                    "practices": [
                        "CloudTrail encrypted with KMS and log file validation enabled",
                        "GuardDuty threat detection with S3 and malware scanning",
                        "SecurityHub with CIS and AWS Foundational benchmarks",
                        "IAM password policy enforces 14-char minimum with rotation",
                        "Account-level S3 public access block prevents accidental exposure",
                    ]
                },
                {
                    "title": "Operational Excellence",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Automated compliance baseline with full audit trail",
                    "practices": [
                        "CloudTrail logs all API activity across all regions",
                        "AWS Config records all resource configuration changes",
                        "SecurityHub provides centralized findings dashboard",
                        "Infrastructure as Code ensures repeatable account setup",
                        "Budget alerts provide proactive cost visibility",
                    ]
                },
                {
                    "title": "Cost Optimization",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Low-cost governance with built-in spend alerting",
                    "practices": [
                        "Budget alerts at 80% and 100% prevent cost overruns",
                        "S3 Glacier lifecycle transitions reduce long-term log costs",
                        "All governance services are pay-per-use with minimal baseline cost",
                        "EBS default encryption uses AWS-managed keys at no extra charge",
                        "Optional default VPC deletion eliminates unused NAT Gateway costs",
                    ]
                },
                {
                    "title": "Reliability",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Managed services with built-in durability and availability",
                    "practices": [
                        "Multi-region CloudTrail ensures global API coverage",
                        "S3 bucket versioning protects against accidental log deletion",
                        "AWS-managed services provide built-in high availability",
                        "Config recorder captures all resource changes for rollback analysis",
                        "KMS key rotation prevents cryptographic key staleness",
                    ]
                },
                {
                    "title": "Sustainability",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Serverless governance layer with minimal resource footprint",
                    "practices": [
                        "All services are fully managed with no idle compute resources",
                        "S3 Glacier lifecycle minimizes active storage energy usage",
                        "Default VPC deletion removes unused networking infrastructure",
                        "Centralized logging avoids duplicate storage across services",
                        "EBS encryption uses hardware acceleration with negligible overhead",
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
                    "default": "my-account",
                    "title": "Project Name",
                    "description": "Used in resource naming across all governance resources",
                    "order": 1,
                    "group": "Essentials",
                    "isEssential": True,
                },
                "environment": {
                    "type": "string",
                    "default": "foundation",
                    "title": "Environment",
                    "description": "Deployment environment label",
                    "enum": ["foundation", "dev", "staging", "prod"],
                    "order": 2,
                    "group": "Essentials",
                    "isEssential": True,
                },
                "region": {
                    "type": "string",
                    "default": "us-east-1",
                    "title": "Primary Region",
                    "description": "AWS region for governance resources",
                    "order": 3,
                    "group": "Essentials",
                    "isEssential": True,
                },
                "enable_guardduty": {
                    "type": "boolean",
                    "default": True,
                    "title": "Enable GuardDuty",
                    "description": "Enable GuardDuty threat detection with S3 and malware scanning",
                    "order": 10,
                    "group": "Security Services",
                },
                "enable_securityhub": {
                    "type": "boolean",
                    "default": True,
                    "title": "Enable SecurityHub",
                    "description": "Enable SecurityHub with CIS and AWS Foundational benchmarks",
                    "order": 11,
                    "group": "Security Services",
                },
                "enable_config": {
                    "type": "boolean",
                    "default": True,
                    "title": "Enable AWS Config",
                    "description": "Enable AWS Config recorder and delivery channel",
                    "order": 12,
                    "group": "Security Services",
                },
                "delete_default_vpc": {
                    "type": "boolean",
                    "default": False,
                    "title": "Delete Default VPC",
                    "description": "Remove the default VPC to enforce explicit network architecture",
                    "order": 13,
                    "group": "Security Services",
                },
                "budget_amount": {
                    "type": "number",
                    "default": 1000,
                    "title": "Monthly Budget (USD)",
                    "description": "Monthly spending limit for budget alerts (80% and 100% thresholds)",
                    "order": 20,
                    "group": "Cost Management",
                    "cost_impact": "Alerts only, no spend cap",
                },
                "budget_email": {
                    "type": "string",
                    "default": "",
                    "title": "Budget Alert Email",
                    "description": "Email address to receive budget threshold notifications",
                    "order": 21,
                    "group": "Cost Management",
                },
                "team_name": {
                    "type": "string",
                    "default": "",
                    "title": "Team Name",
                    "description": "Team that owns this account",
                    "order": 50,
                    "group": "Tags",
                },
            },
            "required": ["project_name"],
        }
