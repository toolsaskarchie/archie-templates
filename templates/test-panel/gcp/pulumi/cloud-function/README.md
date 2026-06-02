# #5 — GCP Cloud Function HTTP (Pulumi, Gen 2)

GCP compute mirror of [#1 AWS Lambda](../../../aws/terraform/lambda-function/README.md).

## What it deploys

- Cloud Storage bucket (source-code archive)
- Storage object (handler zip)
- Cloud Functions v2 (HTTP-triggered, Python 3.11) — serves rotating HTML page
- Cloud Run IAM binding (allUsers as run.invoker — public endpoint)

Conditional (Prod-only):
- Serverless VPC Connector (10.8.0.0/28 in default network)
- Project IAM binding granting function SA roles/vpcaccess.user

## Resource counts

| Profile  | Count |
|----------|-------|
| Non-prod | 4     |
| Prod     | 6 (+VPC connector, +connector IAM = +2) |

## Profiles

### Non-prod

| Field                    | Value     | Lock  | Reason   |
|--------------------------|-----------|-------|----------|
| `memory`                 | "256M"    | LOCK  | GOV-002  |
| `timeout_seconds`        | 30        | LOCK  | GOV-002  |
| `runtime`                | "python311" | LOCK | OPS-002  |
| `enable_vpc_connector`   | false     | LOCK  | GOV-001  |
| `region`                 | "us-central1" | EDIT | —     |
| `page_title`             | (default) | EDIT  | —        |
| `button_color`           | (default) | EDIT  | —        |

### Production

| Field                    | Value     | Lock  | Reason   |
|--------------------------|-----------|-------|----------|
| `memory`                 | "512M"    | LOCK  | OPS-001  |
| `timeout_seconds`        | 60        | LOCK  | OPS-001  |
| `runtime`                | "python311" | LOCK | OPS-002  |
| `enable_vpc_connector`   | true      | LOCK  | SEC-001  |
| `region`                 | "us-central1" | EDIT | —     |
| `page_title`             | (default) | EDIT  | —        |
| `button_color`           | (default) | EDIT  | —        |

## Verifying the deploy

`function_url` output → opens the HTML landing page (same rotating
messages as #1). Refresh cycles the message. The function reads
PAGE_TITLE / BUTTON_COLOR from environment variables so config changes
flow through.

## VPC connector caveat

The `10.8.0.0/28` range is hardcoded. If your default network already
uses that range, the connector creation fails. Override `vpc_cidr_range`
or pre-create the connector outside this blueprint.
