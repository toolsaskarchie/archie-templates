# user-service

The consumer pattern enterprise teams ship per app. Around thirty lines of
HCL, no platform plumbing — the module library does the heavy lifting.

## What this is

This directory is a deployable Terraform root that references
`modules/lambda-service` as a versioned remote module:

```hcl
module "lambda" {
  source = "git::https://github.com/toolsaskarchie/archie-templates.git//templates/terraform/layer2-module-consumer/modules/lambda-service?ref=main"
  ...
}
```

The wrapper exposes exactly five variables — `project_name`, `environment`,
`lambda_memory`, `lambda_timeout`, `tags` — and forwards them to the module.
Everything else (runtime, DLQ, X-Ray, log retention, KMS, alarms, retries)
is the module's job. App teams don't know about those, and don't need to.

## Why it matters for governance

This is the world AskArchie governs. Platform engineers ship the module
library. App teams ship five lines per app. The platform locks the levers
that matter at the app surface, and the module enforces the rest by default.

Compare to Layer 1 (flat templates): the app team would write ~250 lines of
HCL for the same Lambda, and every config knob would be theirs to misuse.

## Outputs

Three values pass through from the module — `function_name`, `function_arn`,
`log_group_name`. Enough for downstream wiring (event sources, alarms,
dashboards) without leaking module internals.

## Provider

The `aws` provider is pinned in `versions.tf` here in the app, and gets
inherited by the module. Standard Terraform pattern — modules don't declare
their own provider configurations, they accept them from the caller.
