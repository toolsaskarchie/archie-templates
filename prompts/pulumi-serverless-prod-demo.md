# Pulumi Serverless (Lambda) — Prod Demo

**Cloud:** AWS
**Engine:** Pulumi (Python)
**Resources:** ~7 (Lambda, Function URL, IAM role + policy, CloudWatch log group, optional SQS DLQ, optional X-Ray)
**Entry point:** Studio → **Generate** (paste the prompt). This is the Pulumi counterpart to the Terraform `templates/terraform/demo/lambda-app` which enters via Studio → **Import**. Same governance story, different engine — proves Archie is engine-agnostic.

## Why this exists

Enterprises mostly run Terraform, so the TF demo enters by *importing* existing code. Few have existing Pulumi to import — so for Pulumi the natural entry point is **Studio AI Generate**. This prompt produces a *prod-grade*, governable Lambda blueprint with the same lever set as the TF demo, so the Govern panel and the deploy → drift → remediate arc look identical.

## Demo arc

1. Studio → Generate → paste prompt → Verify → blueprint with a rich config schema.
2. **Govern**: on the production profile, lock `lambda_memory` 1024, `lambda_timeout` 30, `log_retention_days` 90, `reserved_concurrency` 50, `enable_xray` true, `enable_dlq` true. Non-prod keeps the cheap defaults.
3. Deploy non-prod → fast; outputs echo the effective (governed) values.
4. Deploy/upgrade prod → outputs show the locked floor enforced.
5. Induce drift (lower memory in the console) → drift check → remediate → back in sync.

## Prompt

```
Generate an AWS serverless function blueprint using Pulumi with Python (pulumi and pulumi_aws). Production-grade and fully governable — every operational lever is a config field so a platform engineer can lock it per environment.

Resources:
- Lambda function, Python 3.12, architecture arm64
  - Inline handler that returns an HTML page: background #0B0E14, a bold 42px white message centered, a gray 18px subtitle using the page_title config, and a small "askarchie.io" footer. Each request picks one random line from:
    "Governance in the deploy path, not around it"
    "Your Pulumi stays. We govern on top."
    "5 fields instead of 50"
    "Drift detected. One click to fix."
    "The PE defines the rails. Developers deploy."
  - memory_size from lambda_memory config, timeout from lambda_timeout config
  - reserved_concurrent_executions from reserved_concurrency config (omit the setting when 0)
  - X-Ray active tracing enabled when enable_xray config is true (tracing_config mode Active)
  - environment label surfaced as a Lambda environment variable
- Lambda Function URL, auth type NONE, returns the HTML
- IAM role: least-privilege — assume-role for lambda.amazonaws.com, attach AWSLambdaBasicExecutionRole; add AWSXRayDaemonWriteAccess only when enable_xray is true; add SQS send permission to the DLQ only when enable_dlq is true
- CloudWatch log group named /aws/lambda/<function>, retention_in_days from log_retention_days config
- SQS dead-letter queue created only when enable_dlq config is true, wired as the Lambda dead_letter_config target
- Standard tags on every resource: Project from project_name, Environment from environment, ManagedBy = "Archie"

Config fields (these become the govern schema — keep names and types exact):
- project_name (text, required, description "Resource name prefix. PE-locked.")
- environment (select: nonprod/prod, required, description "Drives the governance profile.")
- lambda_memory (number, default 256, description "Lambda memory in MB. Profile lever — nonprod 256, prod locked higher.")
- lambda_timeout (number, default 15, description "Lambda timeout in seconds. Profile lever.")
- log_retention_days (number, default 7, description "CloudWatch retention in days. Profile lever — nonprod 7, prod 90+.")
- reserved_concurrency (number, default 0, description "Reserved concurrent executions, 0 = unreserved. Profile lever.")
- enable_xray (bool, default false, description "X-Ray tracing. Profile lever — locked on in prod.")
- enable_dlq (bool, default false, description "Dead-letter queue. Profile lever — locked on in prod.")
- page_title (text, default "AskArchie — Agentic Developer Platform", description "Subtitle text on the page.")

Exports (so the stack drawer shows the effective governed config): function_url, function_name, log_group_name, memory_size_mb, timeout_seconds, reserved_concurrency, tracing_enabled, dlq_enabled, dlq_url (null when disabled)

Provider: aws only, region resolved from the deploy environment. Do NOT hardcode credentials or a backend — Archie injects them.

Implementation requirements:
- No nested f-strings and no f-strings around the HTML/JS braces — build the HTML with a plain string and .format() or string concatenation to avoid brace-escape bugs.
- Make enable_xray / enable_dlq / reserved_concurrency truly conditional (resources/permissions only created when on) so non-prod stays minimal.
- Every config value read with a sane default; the blueprint must deploy with no overrides.
```

## Notes

Studio AI is non-deterministic across model/system-prompt versions — **Verify the generated blueprint deploys before demoing**, and if it drifts from this, update this file (per `prompts/README.md`). Pin the working output by publishing it as a catalog blueprint so the live demo doesn't depend on a fresh generation.
