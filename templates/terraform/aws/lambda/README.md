# Lambda Demo — Terraform (AWS)

AWS Lambda + Function URL demo that renders a random AskArchie message as HTML. Includes optional **X-Ray tracing**, **SQS dead letter queue**, and **reserved concurrency** — toggleable via variables so the same template covers dev (cheap, minimal) and prod (observable, resilient) postures without forking.

Designed as the canonical end-to-end demo for the Archie lifecycle: import this from Git, govern it, deploy it, drift-check it, remediate it, upgrade it, rollback it, destroy it.

## Resources

Always present (5):

- `aws_cloudwatch_log_group`
- `aws_iam_role` (Lambda execution)
- `aws_iam_role_policy_attachment` (basic execution)
- `aws_lambda_function` (Python 3.12)
- `aws_lambda_function_url` (HTTPS, NONE auth)
- `aws_lambda_permission` × 2 (URL invoke + function invoke — both required)

Conditional (toggleable via vars):

- `aws_sqs_queue` + `aws_iam_role_policy` (when `enable_dlq = true`)
- `aws_iam_role_policy_attachment` (when `enable_xray = true`)
- `reserved_concurrent_executions` setting (when `reserved_concurrency > 0`)

## Variables

| Name | Default | Description |
|---|---|---|
| `project_name` | `myapp` | Tag prefix and resource name root |
| `environment` | `dev` | Environment label |
| `lambda_memory` | `256` | Lambda memory MB (128-10240) |
| `lambda_timeout` | `15` | Lambda timeout seconds (1-900) |
| `log_retention_days` | `7` | CloudWatch retention (must be valid CW value) |
| `enable_dlq` | `false` | Create SQS dead-letter queue + grant Lambda send permission |
| `enable_xray` | `false` | Enable X-Ray active tracing + attach X-Ray write policy |
| `reserved_concurrency` | `0` | Reserved concurrency limit (0 = no reservation) |
| `page_title` | `AskArchie — Cloud Standards Platform` | Title text on the rendered page |
| `button_color` | `#3B82F6` | Hex color for the refresh button |
| `tags` | `{}` | Additional tags merged into all resources |

## Outputs

| Name | What |
|---|---|
| `function_url` | Public HTTPS URL — open in browser to see the page |
| `function_name` | Lambda function name |
| `log_group_name` | CloudWatch log group |
| `dlq_url` | DLQ URL (null when DLQ disabled) |

## Importing into Archie

1. Studio → **Import & Govern** → Terraform from Git
2. Repo: `https://github.com/toolsaskarchie/archie-templates`
3. Path: `templates/terraform/aws/lambda`
4. Archie parses `variables.tf` → 11 config fields with sensible defaults
5. Lock fields you care about — e.g.:
   - **Non-prod profile:** `enable_dlq = false`, `enable_xray = false`, `reserved_concurrency = 0`, `log_retention_days = 7` (cheap)
   - **Production profile:** `enable_dlq = true`, `enable_xray = true`, `reserved_concurrency = 10`, `log_retention_days = 90` (resilient, observable)
6. Publish → Deploy → open `function_url` in your browser

## Lifecycle demo points

- **Deploy** — 5 to 8 resources depending on toggles, ~30s
- **Drift** — change `log_retention_days` in CloudWatch console, run Check Drift, see the diff
- **Remediate** — one click reverts the manual change back to the blueprint value
- **Upgrade** — bump `button_color` default and republish, then Upgrade the stack
- **Rollback** — pin to prior version, cloud reverts
- **Destroy** — clean teardown, no orphaned IAM or log groups

## Why two Lambda permissions?

When `authorization_type = "NONE"`, you need **both** `lambda:InvokeFunctionUrl` (gates the URL) AND `lambda:InvokeFunction` (gates the function execution). Skipping the second one returns HTTP 403 with a misleading policy that looks correct. Common AWS gotcha.

## Local usage

```bash
terraform init
terraform plan -var="project_name=my-demo"
terraform apply -var="project_name=my-demo"
# open the function_url output in your browser
terraform destroy -var="project_name=my-demo"
```
