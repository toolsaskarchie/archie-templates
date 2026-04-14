"""
AWS Multi-Account Landing Zone (MALZ)

Enterprise-grade multi-account architecture based on AWS MALZ best practices.

Core components:
- AWS Organizations with 6-OU hierarchy
- Service Control Policies (deny root, enforce encryption, region lock, protect guardrails)
- Organization-wide CloudTrail with centralized S3 logging
- AWS Config Aggregator for multi-account compliance
- SecurityHub with CIS + AWS Foundational standards
- GuardDuty organization-wide threat detection
- IAM Identity Center (SSO) with admin + read-only permission sets
- Budget alerts for cost governance

OU Structure (MALZ):
  Root
  ├── Core-Prod          (networking, security, shared services, logging)
  ├── Core-NonProd       (dev networking, shared services)
  ├── Applications-Prod  (web, services, data, infra accounts)
  ├── Applications-NonProd (dev/staging application accounts)
  ├── Isolation          (restricted workloads)
  └── Sandbox            (experimentation, playground)
"""

from typing import Any, Dict, Optional
from pathlib import Path
import json
import pulumi
import pulumi_aws as aws

from provisioner.utils.aws import ResourceNamer
from provisioner.utils.aws.tags import get_standard_tags
from provisioner.templates.base import template_registry, InfrastructureTemplate
from provisioner.templates.template_config import TemplateConfig
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory


@template_registry("aws-landing-zone")
class AWSLandingZoneTemplate(InfrastructureTemplate):
    """
    AWS Multi-Account Landing Zone — Organizations, SCPs, CloudTrail,
    Config, SecurityHub, GuardDuty, IAM Identity Center.
    """

    def __init__(self, name: str = None, config: Dict[str, Any] = None, aws_config: Dict[str, Any] = None, **kwargs):
        raw_config = config or aws_config or kwargs or {}

        if name is None:
            name = (
                raw_config.get('project_name') or
                raw_config.get('projectName') or
                raw_config.get('parameters', {}).get('aws', {}).get('project_name') or
                'landing-zone'
            )

        super().__init__(name, raw_config)

        template_dir = Path(__file__).parent
        self.cfg = TemplateConfig(template_dir, raw_config)
        self.config = raw_config

        # Resource references
        self.organization: Optional[aws.organizations.Organization] = None
        self.org_units: Dict[str, aws.organizations.OrganizationalUnit] = {}
        self.scps: Dict[str, aws.organizations.Policy] = {}
        self.logging_bucket: Optional[aws.s3.BucketV2] = None
        self.trail: Optional[aws.cloudtrail.Trail] = None
        self.guardduty_detector: Optional[aws.guardduty.Detector] = None

    def create_infrastructure(self) -> Dict[str, Any]:
        return self.create()

    def create(self) -> Dict[str, Any]:
        environment = self.cfg.get('environment', 'foundation')
        project_name = self.cfg.project_name
        region = self.cfg.region
        region_short = region.replace('-', '')

        namer = ResourceNamer(
            project=project_name,
            environment=environment,
            region=region,
            template="aws-landing-zone"
        )

        tags = get_standard_tags(
            project=project_name,
            environment=environment,
            template="aws-landing-zone"
        )
        tags.update(self.cfg.get('tags', {}))

        allowed_regions = [r.strip() for r in self.cfg.get('allowed_regions', 'us-east-1,us-west-2,eu-west-1').split(',')]

        # =================================================================
        # LAYER 1: AWS Organizations
        # =================================================================
        print("[LANDING ZONE] Creating AWS Organization...")

        self.organization = factory.create(
            "aws:organizations:Organization",
            f"org-{project_name}",
            feature_set="ALL",
            aws_service_access_principals=[
                "cloudtrail.amazonaws.com",
                "config-multiaccountsetup.amazonaws.com",
                "guardduty.amazonaws.com",
                "securityhub.amazonaws.com",
                "sso.amazonaws.com",
                "ram.amazonaws.com",
                "budgets.amazonaws.com",
            ],
            enabled_policy_types=[
                "SERVICE_CONTROL_POLICY",
                "TAG_POLICY",
            ],
        )

        org_root_id = self.organization.roots[0].id

        # =================================================================
        # LAYER 2: Organizational Units (MALZ Structure)
        # =================================================================
        print("[LANDING ZONE] Creating OU hierarchy...")

        ou_definitions = [
            ("core-prod", "Core-Prod"),
            ("core-nonprod", "Core-NonProd"),
            ("applications-prod", "Applications-Prod"),
            ("applications-nonprod", "Applications-NonProd"),
            ("isolation", "Isolation"),
            ("sandbox", "Sandbox"),
        ]

        for ou_key, ou_name in ou_definitions:
            self.org_units[ou_key] = factory.create(
                "aws:organizations:OrganizationalUnit",
                f"ou-{ou_key}-{project_name}",
                name=ou_name,
                parent_id=org_root_id,
                tags={**tags, "Name": ou_name},
            )

        # =================================================================
        # LAYER 3: Service Control Policies
        # =================================================================
        print("[LANDING ZONE] Creating Service Control Policies...")

        # SCP 1: Deny Root Access
        self.scps["deny-root"] = factory.create(
            "aws:organizations:Policy",
            f"scp-deny-root-{project_name}",
            name="DenyRootAccess",
            type="SERVICE_CONTROL_POLICY",
            description="Deny all actions performed by root user in member accounts",
            content=json.dumps({
                "Version": "2012-10-17",
                "Statement": [{
                    "Sid": "DenyRootAccess",
                    "Effect": "Deny",
                    "Action": "*",
                    "Resource": "*",
                    "Condition": {
                        "StringLike": {"aws:PrincipalArn": "arn:aws:iam::*:root"}
                    }
                }]
            }),
            tags=tags,
        )

        # SCP 2: Enforce Encryption
        self.scps["enforce-encryption"] = factory.create(
            "aws:organizations:Policy",
            f"scp-enforce-encryption-{project_name}",
            name="EnforceEncryption",
            type="SERVICE_CONTROL_POLICY",
            description="Enforce encryption at rest for S3 and EBS",
            content=json.dumps({
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Sid": "DenyUnencryptedS3",
                        "Effect": "Deny",
                        "Action": "s3:PutObject",
                        "Resource": "*",
                        "Condition": {
                            "StringNotEquals": {"s3:x-amz-server-side-encryption": ["aws:kms", "AES256"]},
                            "Null": {"s3:x-amz-server-side-encryption": "false"}
                        }
                    },
                    {
                        "Sid": "DenyUnencryptedEBS",
                        "Effect": "Deny",
                        "Action": "ec2:CreateVolume",
                        "Resource": "*",
                        "Condition": {"Bool": {"ec2:Encrypted": "false"}}
                    }
                ]
            }),
            tags=tags,
        )

        # SCP 3: Region Restriction
        self.scps["region-lock"] = factory.create(
            "aws:organizations:Policy",
            f"scp-region-lock-{project_name}",
            name="RegionRestriction",
            type="SERVICE_CONTROL_POLICY",
            description="Restrict resource creation to approved regions",
            content=json.dumps({
                "Version": "2012-10-17",
                "Statement": [{
                    "Sid": "DenyNonApprovedRegions",
                    "Effect": "Deny",
                    "NotAction": [
                        "iam:*", "organizations:*", "sts:*",
                        "support:*", "budgets:*", "health:*",
                        "cloudfront:*", "route53:*", "waf:*",
                        "ce:*", "s3:GetBucketLocation", "s3:ListAllMyBuckets"
                    ],
                    "Resource": "*",
                    "Condition": {
                        "StringNotEquals": {"aws:RequestedRegion": allowed_regions}
                    }
                }]
            }),
            tags=tags,
        )

        # SCP 4: Protect Guardrails
        self.scps["protect-guardrails"] = factory.create(
            "aws:organizations:Policy",
            f"scp-protect-guardrails-{project_name}",
            name="ProtectGuardrails",
            type="SERVICE_CONTROL_POLICY",
            description="Prevent disabling CloudTrail, Config, GuardDuty, SecurityHub",
            content=json.dumps({
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Sid": "DenyDisableCloudTrail",
                        "Effect": "Deny",
                        "Action": ["cloudtrail:StopLogging", "cloudtrail:DeleteTrail"],
                        "Resource": "*"
                    },
                    {
                        "Sid": "DenyDisableConfig",
                        "Effect": "Deny",
                        "Action": ["config:StopConfigurationRecorder", "config:DeleteConfigurationRecorder"],
                        "Resource": "*"
                    },
                    {
                        "Sid": "DenyDisableGuardDuty",
                        "Effect": "Deny",
                        "Action": ["guardduty:DeleteDetector", "guardduty:DisassociateFromMasterAccount"],
                        "Resource": "*"
                    },
                    {
                        "Sid": "DenyDisableSecurityHub",
                        "Effect": "Deny",
                        "Action": ["securityhub:DisableSecurityHub"],
                        "Resource": "*"
                    }
                ]
            }),
            tags=tags,
        )

        # Attach all SCPs to org root
        for scp_key, scp in self.scps.items():
            factory.create(
                "aws:organizations:PolicyAttachment",
                f"scp-attach-{scp_key}-{project_name}",
                policy_id=scp.id,
                target_id=org_root_id,
            )

        # =================================================================
        # LAYER 4: Centralized Logging (S3 Bucket)
        # =================================================================
        print("[LANDING ZONE] Creating centralized logging bucket...")

        bucket_name = f"archie-logs-{project_name}-{region_short}"

        self.logging_bucket = factory.create(
            "aws:s3:BucketV2",
            f"s3-logging-{project_name}-{region_short}",
            bucket=bucket_name,
            force_destroy=False,
            tags={**tags, "Name": bucket_name, "Purpose": "Centralized Logging"},
        )

        # Versioning
        factory.create(
            "aws:s3:BucketVersioningV2",
            f"s3-logging-versioning-{project_name}",
            bucket=self.logging_bucket.id,
            versioning_configuration={"status": "Enabled"},
        )

        # Encryption
        factory.create(
            "aws:s3:BucketServerSideEncryptionConfigurationV2",
            f"s3-logging-encryption-{project_name}",
            bucket=self.logging_bucket.id,
            rules=[aws.s3.BucketServerSideEncryptionConfigurationV2RuleArgs(
                apply_server_side_encryption_by_default=aws.s3.BucketServerSideEncryptionConfigurationV2RuleApplyServerSideEncryptionByDefaultArgs(
                    sse_algorithm="aws:kms",
                ),
            )],
        )

        # Lifecycle
        retention_days = self.cfg.get('log_retention_days', 365)
        factory.create(
            "aws:s3:BucketLifecycleConfigurationV2",
            f"s3-logging-lifecycle-{project_name}",
            bucket=self.logging_bucket.id,
            rules=[aws.s3.BucketLifecycleConfigurationV2RuleArgs(
                id="archive-old-logs",
                status="Enabled",
                transitions=[aws.s3.BucketLifecycleConfigurationV2RuleTransitionArgs(
                    days=90,
                    storage_class="GLACIER",
                )],
                expiration=aws.s3.BucketLifecycleConfigurationV2RuleExpirationArgs(
                    days=retention_days,
                ),
            )],
        )

        # Block public access
        factory.create(
            "aws:s3:BucketPublicAccessBlock",
            f"s3-logging-public-access-{project_name}",
            bucket=self.logging_bucket.id,
            block_public_acls=True,
            block_public_policy=True,
            ignore_public_acls=True,
            restrict_public_buckets=True,
        )

        # S3 bucket policy for CloudTrail + Config delivery
        account_id = aws.get_caller_identity().account_id
        factory.create(
            "aws:s3:BucketPolicy",
            f"s3-logging-policy-{project_name}",
            bucket=self.logging_bucket.id,
            policy=self.logging_bucket.arn.apply(lambda arn: json.dumps({
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
                        "Resource": f"{arn}/cloudtrail/*",
                        "Condition": {"StringEquals": {"s3:x-amz-acl": "bucket-owner-full-control"}},
                    },
                    {
                        "Sid": "AWSConfigBucketPermissionsCheck",
                        "Effect": "Allow",
                        "Principal": {"Service": "config.amazonaws.com"},
                        "Action": "s3:GetBucketAcl",
                        "Resource": arn,
                    },
                    {
                        "Sid": "AWSConfigBucketDelivery",
                        "Effect": "Allow",
                        "Principal": {"Service": "config.amazonaws.com"},
                        "Action": "s3:PutObject",
                        "Resource": f"{arn}/config/*",
                        "Condition": {"StringEquals": {"s3:x-amz-acl": "bucket-owner-full-control"}},
                    },
                ]
            })),
        )

        # =================================================================
        # LAYER 5: CloudTrail (Organization Trail)
        # =================================================================
        print("[LANDING ZONE] Creating Organization CloudTrail...")

        trail_name = f"archie-trail-{project_name}-{region_short}"
        self.trail = factory.create(
            "aws:cloudtrail:Trail",
            f"trail-org-{project_name}-{region_short}",
            name=trail_name,
            is_organization_trail=True,
            is_multi_region_trail=True,
            enable_log_file_validation=True,
            s3_bucket_name=self.logging_bucket.bucket,
            s3_key_prefix="cloudtrail",
            include_global_service_events=True,
            tags={**tags, "Name": trail_name},
            opts=pulumi.ResourceOptions(depends_on=[self.logging_bucket]),
        )

        # =================================================================
        # LAYER 6: AWS Config (Aggregator)
        # =================================================================
        print("[LANDING ZONE] Creating AWS Config Aggregator...")

        # Config IAM role
        config_role = factory.create(
            "aws:iam:Role",
            f"role-config-{project_name}",
            name=f"archie-config-{project_name}",
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
            f"role-config-policy-{project_name}",
            role=config_role.name,
            policy_arn="arn:aws:iam::aws:policy/service-role/AWS_ConfigRole",
        )

        aggregator_name = f"archie-aggregator-{project_name}"
        factory.create(
            "aws:cfg:ConfigurationAggregator",
            f"config-aggregator-{project_name}",
            name=aggregator_name,
            organization_aggregation_source=aws.cfg.ConfigurationAggregatorOrganizationAggregationSourceArgs(
                all_regions=True,
                role_arn=config_role.arn,
            ),
        )

        # =================================================================
        # LAYER 7: SecurityHub (Optional)
        # =================================================================
        securityhub_arn = None
        if self.cfg.get('enable_securityhub', True):
            print("[LANDING ZONE] Enabling SecurityHub with CIS + AWS Foundational standards...")

            hub = factory.create(
                "aws:securityhub:Account",
                f"securityhub-{project_name}",
            )

            factory.create(
                "aws:securityhub:OrganizationConfiguration",
                f"securityhub-org-{project_name}",
                auto_enable=True,
                opts=pulumi.ResourceOptions(depends_on=[hub]),
            )

            # CIS Benchmark
            factory.create(
                "aws:securityhub:StandardsSubscription",
                f"securityhub-cis-{project_name}",
                standards_arn="arn:aws:securityhub:::ruleset/cis-aws-foundations-benchmark/v/1.4.0",
                opts=pulumi.ResourceOptions(depends_on=[hub]),
            )

            # AWS Foundational Best Practices
            factory.create(
                "aws:securityhub:StandardsSubscription",
                f"securityhub-aws-foundational-{project_name}",
                standards_arn="arn:aws:securityhub:::standards/aws-foundational-security-best-practices/v/1.0.0",
                opts=pulumi.ResourceOptions(depends_on=[hub]),
            )

            securityhub_arn = hub.arn

        # =================================================================
        # LAYER 8: GuardDuty (Optional)
        # =================================================================
        guardduty_detector_id = None
        if self.cfg.get('enable_guardduty', True):
            print("[LANDING ZONE] Enabling GuardDuty with S3 + K8s + Malware protection...")

            self.guardduty_detector = factory.create(
                "aws:guardduty:Detector",
                f"guardduty-detector-{project_name}",
                enable=True,
                finding_publishing_frequency="FIFTEEN_MINUTES",
                datasources=aws.guardduty.DetectorDatasourcesArgs(
                    s3_logs=aws.guardduty.DetectorDatasourcesS3LogsArgs(enable=True),
                    kubernetes=aws.guardduty.DetectorDatasourcesKubernetesArgs(
                        audit_logs=aws.guardduty.DetectorDatasourcesKubernetesAuditLogsArgs(enable=True),
                    ),
                    malware_protection=aws.guardduty.DetectorDatasourcesMalwareProtectionArgs(
                        scan_ec2_instance_with_findings=aws.guardduty.DetectorDatasourcesMalwareProtectionScanEc2InstanceWithFindingsArgs(
                            ebs_volumes=aws.guardduty.DetectorDatasourcesMalwareProtectionScanEc2InstanceWithFindingsEbsVolumesArgs(enable=True),
                        ),
                    ),
                ),
            )

            factory.create(
                "aws:guardduty:OrganizationConfiguration",
                f"guardduty-org-{project_name}",
                detector_id=self.guardduty_detector.id,
                auto_enable_organization_members="ALL",
            )

            guardduty_detector_id = self.guardduty_detector.id

        # =================================================================
        # LAYER 9: IAM Identity Center / SSO (Optional)
        # =================================================================
        sso_admin_arn = None
        sso_readonly_arn = None
        if self.cfg.get('enable_sso', True):
            print("[LANDING ZONE] Configuring IAM Identity Center permission sets...")

            # Get SSO instance (auto-created when Organizations + SSO is enabled)
            sso_instances = aws.ssoadmin.get_instances()
            if sso_instances.arns:
                sso_instance_arn = sso_instances.arns[0]

                admin_ps = factory.create(
                    "aws:ssoadmin:PermissionSet",
                    f"sso-admin-ps-{project_name}",
                    name="AdministratorAccess",
                    description="Full administrator access for platform engineers",
                    instance_arn=sso_instance_arn,
                    session_duration="PT8H",
                    relay_state="https://console.aws.amazon.com/",
                )

                factory.create(
                    "aws:ssoadmin:ManagedPolicyAttachment",
                    f"sso-admin-policy-{project_name}",
                    instance_arn=sso_instance_arn,
                    permission_set_arn=admin_ps.arn,
                    managed_policy_arn="arn:aws:iam::aws:policy/AdministratorAccess",
                )

                readonly_ps = factory.create(
                    "aws:ssoadmin:PermissionSet",
                    f"sso-readonly-ps-{project_name}",
                    name="ReadOnlyAccess",
                    description="Read-only access for developers and auditors",
                    instance_arn=sso_instance_arn,
                    session_duration="PT8H",
                )

                factory.create(
                    "aws:ssoadmin:ManagedPolicyAttachment",
                    f"sso-readonly-policy-{project_name}",
                    instance_arn=sso_instance_arn,
                    permission_set_arn=readonly_ps.arn,
                    managed_policy_arn="arn:aws:iam::aws:policy/ReadOnlyAccess",
                )

                sso_admin_arn = admin_ps.arn
                sso_readonly_arn = readonly_ps.arn
            else:
                print("[LANDING ZONE] ⚠ IAM Identity Center not available — enable SSO in Organizations first")

        # =================================================================
        # LAYER 10: Budget Alerts (Optional)
        # =================================================================
        if self.cfg.get('enable_budget_alerts', True):
            monthly_budget = str(self.cfg.get('monthly_budget', 10000))
            print(f"[LANDING ZONE] Creating budget alert (${monthly_budget}/month)...")

            factory.create(
                "aws:budgets:Budget",
                f"budget-org-{project_name}",
                name=f"archie-budget-{project_name}",
                budget_type="COST",
                limit_amount=monthly_budget,
                limit_unit="USD",
                time_unit="MONTHLY",
                notifications=[
                    aws.budgets.BudgetNotificationArgs(
                        comparison_operator="GREATER_THAN",
                        threshold=80,
                        threshold_type="PERCENTAGE",
                        notification_type="ACTUAL",
                    ),
                    aws.budgets.BudgetNotificationArgs(
                        comparison_operator="GREATER_THAN",
                        threshold=100,
                        threshold_type="PERCENTAGE",
                        notification_type="ACTUAL",
                    ),
                ],
            )

        # =================================================================
        # OUTPUTS
        # =================================================================
        print("[LANDING ZONE] ✅ Landing Zone deployment complete!")

        outputs = {
            "organization_id": self.organization.id,
            "organization_arn": self.organization.arn,
            "organization_root_id": org_root_id,
            "ou_core_prod_id": self.org_units["core-prod"].id,
            "ou_core_nonprod_id": self.org_units["core-nonprod"].id,
            "ou_applications_prod_id": self.org_units["applications-prod"].id,
            "ou_applications_nonprod_id": self.org_units["applications-nonprod"].id,
            "ou_isolation_id": self.org_units["isolation"].id,
            "ou_sandbox_id": self.org_units["sandbox"].id,
            "scp_deny_root_id": self.scps["deny-root"].id,
            "scp_enforce_encryption_id": self.scps["enforce-encryption"].id,
            "scp_region_lock_id": self.scps["region-lock"].id,
            "scp_protect_guardrails_id": self.scps["protect-guardrails"].id,
            "cloudtrail_arn": self.trail.arn,
            "logging_bucket_name": self.logging_bucket.bucket,
            "logging_bucket_arn": self.logging_bucket.arn,
            "config_aggregator_name": aggregator_name,
        }

        if guardduty_detector_id:
            outputs["guardduty_detector_id"] = guardduty_detector_id
        if securityhub_arn:
            outputs["securityhub_arn"] = securityhub_arn
        if sso_admin_arn:
            outputs["sso_admin_permission_set_arn"] = sso_admin_arn
        if sso_readonly_arn:
            outputs["sso_readonly_permission_set_arn"] = sso_readonly_arn

        # Export all outputs
        for key, value in outputs.items():
            pulumi.export(key, value)

        return outputs

    def get_outputs(self) -> Dict[str, Any]:
        """Get template outputs"""
        if not self.organization:
            return {}

        outputs = {
            "organization_id": self.organization.id,
            "organization_arn": self.organization.arn,
            "logging_bucket_name": self.logging_bucket.bucket if self.logging_bucket else None,
            "logging_bucket_arn": self.logging_bucket.arn if self.logging_bucket else None,
            "cloudtrail_arn": self.trail.arn if self.trail else None,
        }

        for ou_key, ou in self.org_units.items():
            outputs[f"ou_{ou_key.replace('-', '_')}_id"] = ou.id

        for scp_key, scp in self.scps.items():
            outputs[f"scp_{scp_key.replace('-', '_')}_id"] = scp.id

        if self.guardduty_detector:
            outputs["guardduty_detector_id"] = self.guardduty_detector.id

        return outputs

    @classmethod
    def get_metadata(cls) -> Dict[str, Any]:
        """Template metadata for marketplace registration"""
        return {
            "name": "aws-landing-zone",
            "title": "Multi-Account Landing Zone",
            "description": "Enterprise-grade multi-account architecture based on AWS MALZ best practices. Provisions Organizations, SCPs, CloudTrail, Config, SecurityHub, GuardDuty, and IAM Identity Center.",
            "category": "governance",
            "version": "1.0.0",
            "author": "InnovativeApps",
            "cloud": "aws",
            "environment": "foundation",
            "base_cost": "$10/month",
            "tags": ["organizations", "landing-zone", "governance", "security", "compliance"],
            "features": [
                "AWS Organizations with 6-OU MALZ hierarchy",
                "Service Control Policies for guardrail enforcement",
                "Organization-wide CloudTrail with centralized logging",
                "GuardDuty threat detection across all accounts",
                "IAM Identity Center with admin and read-only permission sets"
            ],
            "deployment_time": "10-15 minutes",
            "complexity": "advanced",
            "use_cases": [
                "Enterprise AWS multi-account setup",
                "Security and compliance baseline",
                "CIS Benchmark alignment for new organizations",
                "Centralized governance and cost management",
            ],
            "pillars": [
                {
                    "title": "Operational Excellence",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Centralized governance with automated multi-account management",
                    "practices": [
                        "AWS Organizations provides centralized multi-account management",
                        "AWS Config Aggregator for organization-wide compliance visibility",
                        "Automated OU structure follows AWS MALZ best practices",
                        "Infrastructure as Code for repeatable landing zone deployments",
                        "Budget alerts for proactive cost governance"
                    ]
                },
                {
                    "title": "Security",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Defense-in-depth with SCPs, GuardDuty, and SecurityHub",
                    "practices": [
                        "Service Control Policies enforce guardrails across all accounts",
                        "GuardDuty provides organization-wide threat detection",
                        "SecurityHub with CIS and AWS Foundational benchmarks",
                        "CloudTrail logs all API activity with log file validation",
                        "Encryption enforcement SCP prevents unencrypted S3 and EBS"
                    ]
                },
                {
                    "title": "Reliability",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Resilient governance services with centralized logging",
                    "practices": [
                        "Multi-region CloudTrail ensures no API calls are missed",
                        "S3 logging bucket with versioning for data durability",
                        "Guardrail protection SCP prevents disabling security services",
                        "AWS-managed services provide built-in high availability",
                        "Glacier lifecycle policies ensure long-term log retention"
                    ]
                },
                {
                    "title": "Performance Efficiency",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Lightweight governance layer with minimal overhead",
                    "practices": [
                        "Organizations and SCPs add zero latency to workloads",
                        "Config Aggregator efficiently collects compliance data",
                        "GuardDuty uses ML-based analysis with no agent overhead",
                        "IAM Identity Center provides fast SSO access to accounts",
                        "Region restriction SCP reduces blast radius and simplifies management"
                    ]
                },
                {
                    "title": "Cost Optimization",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Low-cost governance with built-in budget alerting",
                    "practices": [
                        "AWS Organizations is free for multi-account management",
                        "Budget alerts notify at 80% and 100% spend thresholds",
                        "Glacier lifecycle transitions reduce long-term log storage costs",
                        "Region restriction prevents accidental resource sprawl",
                        "IAM Identity Center is included at no additional charge"
                    ]
                },
                {
                    "title": "Sustainability",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Serverless governance services minimize resource consumption",
                    "practices": [
                        "All governance services are fully managed with no idle compute",
                        "Region restriction reduces unnecessary infrastructure sprawl",
                        "Centralized logging eliminates duplicate log storage across accounts",
                        "S3 Glacier lifecycle minimizes active storage energy usage",
                        "Shared AWS infrastructure for Organizations and Identity Center"
                    ]
                }
            ]
        }

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        """Get configuration schema for the UI"""
        return {
            "type": "object",
            "properties": {
                "project_name": {
                    "type": "string",
                    "default": "my-org",
                    "title": "Organization Name",
                    "description": "Name for the landing zone organization",
                    "order": 1,
                    "group": "Essentials"
                },
                "region": {
                    "type": "string",
                    "default": "us-east-1",
                    "title": "Primary Region",
                    "description": "AWS region for landing zone resources",
                    "order": 2,
                    "group": "Essentials"
                },
                "allowed_regions": {
                    "type": "string",
                    "default": "us-east-1,us-west-2,eu-west-1",
                    "title": "Allowed Regions",
                    "description": "Comma-separated list of regions workloads can deploy to",
                    "order": 10,
                    "group": "Governance"
                },
                "enable_securityhub": {
                    "type": "boolean",
                    "default": True,
                    "title": "Enable SecurityHub",
                    "description": "Enable AWS SecurityHub with CIS and Foundational benchmarks",
                    "order": 20,
                    "group": "Security"
                },
                "enable_guardduty": {
                    "type": "boolean",
                    "default": True,
                    "title": "Enable GuardDuty",
                    "description": "Enable GuardDuty threat detection across all accounts",
                    "order": 21,
                    "group": "Security"
                },
                "enable_sso": {
                    "type": "boolean",
                    "default": True,
                    "title": "Enable IAM Identity Center",
                    "description": "Configure SSO permission sets for admin and read-only access",
                    "order": 22,
                    "group": "Security"
                },
                "enable_budget_alerts": {
                    "type": "boolean",
                    "default": True,
                    "title": "Enable Budget Alerts",
                    "description": "Create monthly budget with 80% and 100% threshold alerts",
                    "order": 30,
                    "group": "Cost Management"
                },
                "monthly_budget": {
                    "type": "number",
                    "default": 10000,
                    "title": "Monthly Budget (USD)",
                    "description": "Monthly spending limit for budget alerts",
                    "order": 31,
                    "group": "Cost Management"
                },
                "log_retention_days": {
                    "type": "number",
                    "default": 365,
                    "title": "Log Retention (Days)",
                    "description": "Number of days to retain CloudTrail and Config logs",
                    "order": 40,
                    "group": "Logging"
                },
                "team_name": {
                    "type": "string",
                    "default": "",
                    "title": "Team Name",
                    "description": "Team that owns this resource",
                    "order": 50,
                    "group": "Tags",
                },
            },
            "required": ["project_name", "region"]
        }
