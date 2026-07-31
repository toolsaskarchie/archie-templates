# Platform Foundation — Terraform (AWS)

A governed application landing zone on AWS — network, storage, identity, messaging, and logging in one blueprint. Designed as a clean import target for Archie Studio's "Import from Git" flow: essential inputs (`project_name`, `environment`) have no defaults so the deployer supplies them, while every governed knob carries a safe default and is meant to be locked per policy. Public ingress (`0.0.0.0/0`) is rejected by an input validation.

## Resources (~17)

- VPC with a public subnet, internet gateway, route table + association
- Security group (corporate-CIDR ingress only, all egress)
- S3 assets bucket with versioning, lifecycle expiry, SSE encryption, and public-access block
- DynamoDB config table (point-in-time recovery)
- SQS events queue + SNS notifications topic
- Least-privilege application IAM role + inline policy
- CloudWatch log group (retention governed)

## Variables

| Name | Default | Description |
|---|---|---|
| `project_name` | _(required)_ | Short project/app name; drives all resource naming (3–32 lowercase alnum/hyphen) |
| `environment` | _(required)_ | Deployment environment: `nonprod` or `prod` |
| `region` | `us-east-1` | AWS region for all resources |
| `vpc_cidr` | `10.0.0.0/16` | CIDR block for the platform VPC |
| `allowed_ingress_cidr` | `10.0.0.0/8` | CIDR permitted to reach the app SG (public rejected) |
| `s3_versioning_enabled` | `true` | Object versioning on the assets bucket |
| `s3_noncurrent_expiration_days` | `90` | Days before noncurrent versions expire |
| `dynamodb_point_in_time_recovery` | `true` | PITR on the config table |
| `sqs_message_retention_seconds` | `345600` | SQS message retention (seconds) |
| `log_retention_days` | `30` | CloudWatch log group retention (days) |
| `tags` | `{ CostCenter = "platform-engineering" }` | Additional tags merged into enterprise defaults |

## Outputs

| Name | What |
|---|---|
| `region` | AWS region this stack deployed into |
| `vpc_id` | Platform VPC id |
| `assets_bucket` | Assets S3 bucket name |
| `config_table` | Config DynamoDB table name |
| `events_queue_url` | SQS events queue URL |
| `notifications_topic_arn` | SNS notifications topic ARN |
| `app_role_arn` | Least-privilege application IAM role ARN |

## Importing into Archie

1. Studio → Import → Terraform from Git
2. Repo: `https://github.com/toolsaskarchie/archie-templates`
3. Path: `templates/terraform/aws/platform-foundation`
4. Studio parses `variables.tf`, infers the config schema, creates a draft blueprint
5. Lock fields (region, CIDRs, retention), set per-env defaults, publish → governed
6. Deploy via UI or agent
