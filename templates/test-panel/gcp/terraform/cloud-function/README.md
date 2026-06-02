# #6 — GCP Cloud Function HTTP (TF, Gen 2)

TF mirror of [#5](../../pulumi/cloud-function/README.md). Same resources,
same conditional gates, same demo HTML landing page as all five sibling
blueprints.

## What it deploys

- Cloud Storage bucket (source archive)
- Storage bucket object (handler zip)
- Cloud Functions v2 (HTTP-triggered, Python 3.11)
- Cloud Run IAM binding (allUsers as run.invoker — public endpoint)

Conditional (Prod-only):
- Serverless VPC Connector (10.8.0.0/28 in default network)
- Project IAM binding granting function runtime SA `roles/vpcaccess.user`

## Resource counts

| Profile  | Count |
|----------|-------|
| Non-prod | 4     |
| Prod     | 6 (+VPC connector, +IAM binding = +2) |

## Profiles

### Non-prod

| Field                    | Value         | Lock  | Reason   |
|--------------------------|---------------|-------|----------|
| `memory`                 | "256M"        | LOCK  | GOV-002  |
| `timeout_seconds`        | 30            | LOCK  | GOV-002  |
| `runtime`                | "python311"   | LOCK  | OPS-002  |
| `enable_vpc_connector`   | false         | LOCK  | GOV-001  |
| `region`                 | "us-central1" | EDIT  | —        |
| `page_title`             | (default)     | EDIT  | —        |
| `button_color`           | (default)     | EDIT  | —        |
| `gcp_project`            | (required)    | EDIT  | —        |

### Production

| Field                    | Value         | Lock  | Reason   |
|--------------------------|---------------|-------|----------|
| `memory`                 | "512M"        | LOCK  | OPS-001  |
| `timeout_seconds`        | 60            | LOCK  | OPS-001  |
| `runtime`                | "python311"   | LOCK  | OPS-002  |
| `enable_vpc_connector`   | true          | LOCK  | SEC-001  |
| `region`                 | "us-central1" | EDIT  | —        |
| `page_title`             | (default)     | EDIT  | —        |
| `button_color`           | (default)     | EDIT  | —        |
| `gcp_project`            | (required)    | EDIT  | —        |

## Verifying the deploy

After successful deploy, the output `function_url` opens the demo HTML
page — same dark theme + 10 rotating AskArchie messages + "Show me
another" button as all other compute blueprints. Refresh cycles the
message; the URL is the Cloud Run service URL provisioned by Gen 2.

## VPC connector caveat

`10.8.0.0/28` is hardcoded. If your default network already uses that
range, the connector creation fails. Either override (currently not
exposed — wire it up if you need a different range) or pre-create the
connector outside this blueprint and skip enable_vpc_connector.

## Drift inject

See header comment in `main.tf` for the CLI matrix.
