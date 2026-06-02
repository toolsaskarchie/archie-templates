# #2 — AWS Lambda + Function URL (Pulumi)

Pulumi mirror of [#1](../../terraform/lambda-function/README.md). Same
resources, same HTML page, same drift surface — lets us validate the Pulumi
engine path against an identical-shape stack.

## What it deploys

- IAM role + basic execution attachment
- CloudWatch log group (retention configurable)
- Lambda function (Python 3.12) — serves HTML rotating-message landing page
- Lambda Function URL (public, CORS GET *)
- 2× Lambda permissions (URL invoke + invoke)

Conditional (Prod only):
- SQS Dead Letter Queue + role policy
- X-Ray role attachment + tracing config block

## Resource counts

| Profile  | Count |
|----------|-------|
| Non-prod | 7     |
| Prod     | 9 (+SQS DLQ, +X-Ray attach = +2) |

## Profiles

Same field set + lock vocabulary as #1. See [#1 README](../../terraform/lambda-function/README.md#profiles) — Pulumi config keys are the same names.

## Drift inject + verify

See header docstring in `__main__.py` for the CLI matrix — identical to #1.
