# #1 — AWS Lambda + Function URL (TF)

**Reference blueprint** for the test-panel pattern. Other blueprints mirror
this structure.

## What it deploys

- IAM role for Lambda execution
- CloudWatch log group (retention configurable)
- Lambda function (Python 3.12) — serves a rotating-message HTML page
- Lambda Function URL (no auth, public)
- Lambda permissions (URL invoke + function invoke)

Conditional (Prod only by default):
- SQS Dead Letter Queue + IAM policy attachment
- X-Ray tracing config + IAM policy attachment

## Resource counts

| Profile  | Count |
|----------|-------|
| Non-prod | 7     |
| Prod     | 9 (+SQS DLQ, +X-Ray policy = +2) |

## Profiles (set these in the Blueprint Editor after import)

### Non-prod

| Field                 | Value     | Lock  | Reason     |
|-----------------------|-----------|-------|------------|
| `lambda_memory`       | 128       | LOCK  | GOV-002    |
| `lambda_timeout`      | 15        | LOCK  | GOV-002    |
| `log_retention_days`  | 3         | LOCK  | OPS-001    |
| `enable_dlq`          | false     | LOCK  | GOV-001    |
| `enable_xray`         | false     | LOCK  | GOV-001    |
| `reserved_concurrency`| 0         | EDIT  | —          |
| `page_title`          | (default) | EDIT  | —          |
| `button_color`        | (default) | EDIT  | —          |

### Production

| Field                 | Value      | Lock  | Reason     |
|-----------------------|------------|-------|------------|
| `lambda_memory`       | 512        | LOCK  | OPS-001    |
| `lambda_timeout`      | 30         | LOCK  | OPS-001    |
| `log_retention_days`  | 90         | LOCK  | SEC-002    |
| `enable_dlq`          | true       | LOCK  | SEC-001    |
| `enable_xray`         | true       | LOCK  | SEC-001    |
| `reserved_concurrency`| 50         | EDIT  | —          |
| `page_title`          | (default)  | EDIT  | —          |
| `button_color`        | (default)  | EDIT  | —          |

## Verifying the deploy

After successful deploy, the output `function_url` opens the HTML landing
page in a browser. Refresh cycles through 10 rotating AskArchie messages.
The page also shows `PAGE_TITLE` (project subtitle) so you can confirm
config values landed.

## Drift inject + verify

See header comment in `main.tf` for the CLI matrix. Quick check:

```bash
# Inject
aws lambda update-function-configuration \
  --function-name $PROJECT-$ENV-function \
  --memory-size 512

# Wait for scheduled drift OR click "Check Drift" in Archie
# Drift report should show: memory_size: 128 → 512

# Remediate via Archie UI → cloud goes back to 128
```

## Known noise to NOT inject

- `aws_iam_role.managed_policy_arns` — populated by separate `policy_attachment` resource; always shows null→["arn"]
- `aws_lambda_function.layers` — AWS returns `[]` for the unset list; always shows null→[]

Both are filtered by `engine.py` computed_fields list — confirm filters still
trip if you see them appear in a drift report.
