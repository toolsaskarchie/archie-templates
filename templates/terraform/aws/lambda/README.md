# Lambda Demo — Terraform (AWS)

AWS Lambda + Function URL + DynamoDB demo. Self-contained AskArchie pitch page that picks a random message from a list and renders it as HTML. No external dependencies, no VPC, no NAT — deploys clean in ~30s, costs ~$0/mo at idle.

Designed as the canonical end-to-end demo for the Archie lifecycle: import this from Git, govern it, deploy it, drift-check it, remediate it, upgrade it, rollback it, destroy it.

## Resources (~9)

- `aws_dynamodb_table` (provisioned, configurable RCU/WCU)
- `aws_iam_role` (Lambda execution role)
- `aws_iam_role_policy_attachment` (basic execution)
- `aws_iam_role_policy` (DynamoDB read/write/scan)
- `aws_cloudwatch_log_group` (with retention)
- `aws_lambda_function` (Python 3.12, arm64)
- `aws_lambda_function_url` (HTTPS, NONE auth)
- `aws_lambda_permission` × 2 (URL invoke + function invoke — both required)

## Variables

| Name | Default | Description |
|---|---|---|
| `project_name` | `archie-demo` | Tag prefix and resource name root |
| `environment` | `dev` | Environment label (dev / staging / production) |
| `lambda_memory` | `256` | Lambda memory MB (128-10240) |
| `lambda_timeout` | `30` | Lambda timeout seconds (1-900) |
| `auth_type` | `NONE` | Function URL auth (`NONE` for public, `AWS_IAM` for signed) |
| `button_color` | `#3B82F6` | Hex color for the refresh button |
| `page_title` | `AskArchie — Cloud Standards Platform` | Title + subtitle text |
| `log_retention_days` | `7` | CloudWatch log retention |
| `table_name` | `archie-demo-table` | DynamoDB table name |
| `partition_key` | `id` | DynamoDB hash key attribute name |
| `read_capacity` | `5` | DynamoDB RCU |
| `write_capacity` | `5` | DynamoDB WCU |
| `tags` | `{}` | Additional tags merged into all resources |

## Outputs

| Name | What |
|---|---|
| `function_url` | Public HTTPS URL — open in browser to see the page |
| `function_name` | Lambda function name |
| `function_arn` | Lambda function ARN |
| `log_group_name` | CloudWatch log group |
| `execution_role_arn` | Lambda execution role ARN |
| `table_name` | DynamoDB table name |
| `table_arn` | DynamoDB table ARN |

## Importing into Archie

1. Studio → **Import & Govern** → Terraform from Git
2. Repo: `https://github.com/toolsaskarchie/archie-templates`
3. Path: `templates/terraform/aws/lambda`
4. Archie parses `variables.tf` → 12 config fields with sensible defaults
5. Lock fields if you want (e.g. lock `auth_type` to `AWS_IAM` for prod, lock `log_retention_days` to 30+)
6. Publish → Deploy → open the `function_url` output in your browser

## Lifecycle demo points

This template covers every step of the Archie lifecycle:

- **Deploy** — 9 resources, ~30s
- **Drift** — change `log_retention_days` in the AWS console, run Check Drift, see the diff
- **Remediate** — one click reverts the manual change back to the blueprint value
- **Upgrade** — bump `button_color` default and republish, then Upgrade the stack
- **Rollback** — pin to the prior version, cloud reverts
- **Destroy** — clean teardown, no orphaned IAM or log groups

## Why Function URL (not API Gateway)?

For demos: no extra cost, no extra resource to set up, no domain config. Function URL gives you HTTPS + CORS out of the box. For real production traffic, fork this and swap in API Gateway / CloudFront in front.

## Why two Lambda permissions?

When `authorization_type = "NONE"`, you need **both** `lambda:InvokeFunctionUrl` (gates the URL) AND `lambda:InvokeFunction` (gates the function execution). Skipping the second one returns HTTP 403 with a misleading policy that looks correct. Common AWS gotcha — see comments in `main.tf`.

## Local usage

```bash
terraform init
terraform plan -var="project_name=my-demo"
terraform apply -var="project_name=my-demo"
# open the function_url output in your browser
terraform destroy -var="project_name=my-demo"
```
