# #3 — Azure Function App (TF, Consumption plan)

Quota-safe Azure compute mirror of [#1 AWS Lambda](../../../aws/terraform/lambda-function/README.md).

## What it deploys

- Resource Group
- Storage Account (LRS — no quota cost)
- Service Plan (Y1 Consumption — no VM quota)
- Linux Function App (Python) — serves rotating HTML landing page

Conditional (Prod-only):
- Application Insights (web app type, 90-day retention)
- Storage container "staging-slot-marker" (mimics Prod's slot resource; real slot needs Premium plan which exceeds sandbox quota)

## Resource counts

| Profile  | Count |
|----------|-------|
| Non-prod | 5     |
| Prod     | 7 (+App Insights, +slot marker = +2) |

## Quota safety

Azure sandbox accounts cap VM cores at 4 and Standard LBs at 0-1.
This blueprint uses none of those — Consumption plan + Storage + Function
App alone, all sandbox-friendly.

## Profiles

### Non-prod

| Field                  | Value     | Lock  | Reason   |
|------------------------|-----------|-------|----------|
| `runtime_version`      | "3.11"    | LOCK  | OPS-002  |
| `enable_app_insights`  | false     | LOCK  | GOV-001  |
| `enable_slot`          | false     | LOCK  | GOV-001  |
| `always_on`            | false     | LOCK  | GOV-002  |
| `location`             | "eastus"  | EDIT  | —        |
| `page_title`           | (default) | EDIT  | —        |
| `button_color`         | (default) | EDIT  | —        |

### Production

| Field                  | Value     | Lock  | Reason   |
|------------------------|-----------|-------|----------|
| `runtime_version`      | "3.11"    | LOCK  | OPS-002  |
| `enable_app_insights`  | true      | LOCK  | SEC-001  |
| `enable_slot`          | true      | LOCK  | OPS-001  |
| `always_on`            | false     | LOCK  | (Y1 plan doesn't support) |
| `location`             | "eastus"  | EDIT  | —        |
| `page_title`           | (default) | EDIT  | —        |
| `button_color`         | (default) | EDIT  | —        |

## Verifying the deploy

After successful deploy, the output `function_url` opens the HTML landing
page (same rotating messages as #1). Refresh cycles the message.

## Drift inject

See header comment block in `main.tf` for the CLI matrix.
