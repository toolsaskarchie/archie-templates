"""
─── Test Panel: AWS Lambda + Function URL (Pulumi) ──────────────────────────
Mirror of #1 (templates/test-panel/aws/terraform/lambda-function) — same
resources, same conditional gates, same HTML landing page. Lets us test the
Pulumi lifecycle path against an identical-shape stack.

Resources per profile:
  Non-prod:  7  (log group, role, basic-attach, function, url, url-perm × 2)
  Prod:      9  (+ X-Ray attach + SQS DLQ = +2 over nonprod)

Drift-injectable fields (validated to surface as drift + remediate cleanly):
  memory_size         → boto3.update_function_configuration MemorySize=N
  timeout             → boto3.update_function_configuration Timeout=N
  log retention       → boto3.put_retention_policy retentionInDays=N
  env PAGE_TITLE      → boto3.update_function_configuration Environment.Variables

Drift noise (do NOT inject — known false positives):
  - managedPolicyArns on role  (populated by separate RolePolicyAttachment)
  - layers: null → []          (AWS returns empty list for unset optional)
"""
import base64
import io
import json
import zipfile

import pulumi
import pulumi_aws as aws

config = pulumi.Config()


def cfg(key: str, fallback=None, *, secret: bool = False):
    """Read config with fallback. Matches the cfg() pattern from #265."""
    try:
        if secret:
            v = config.get_secret(key)
            return v if v is not None else fallback
        return config.get(key) or fallback
    except Exception:
        return fallback


# ── Config ────────────────────────────────────────────────────────────────
project_name = cfg("project_name", "myapp")
environment = cfg("environment", "dev")
lambda_memory = int(cfg("lambda_memory", 256))
lambda_timeout = int(cfg("lambda_timeout", 15))
log_retention_days = int(cfg("log_retention_days", 7))
enable_dlq = str(cfg("enable_dlq", "false")).lower() == "true"
enable_xray = str(cfg("enable_xray", "false")).lower() == "true"
reserved_concurrency = int(cfg("reserved_concurrency", 0))
page_title = cfg("page_title", "AskArchie — Cloud Standards Platform")
button_color = cfg("button_color", "#3B82F6")

common_tags = {
    "Project": project_name,
    "Environment": environment,
    "ManagedBy": "Archie",
}

# ── Handler code (identical HTML landing page to #1 TF) ───────────────────
HANDLER_SRC = """
import json
import os
import random


def lambda_handler(event, context):
    messages = [
        "Governance in the deploy path, not around it",
        "5 fields instead of 50",
        "Drift detected. One click to fix.",
        "The developer deploys. The PE defines the rules.",
        "Your Terraform stays. We govern on top.",
        "Deploy blocked: unresolved drift. Remediate first.",
        "9 resources. 10 config fields. One click.",
        "The real complexity starts the day after deploy.",
        "Detection is solved. The gap is between detected and fixed.",
        "Describe. Generate. Govern. Deploy.",
    ]

    page_title = os.environ.get("PAGE_TITLE", "AskArchie")
    button_color = os.environ.get("BUTTON_COLOR", "#3B82F6")
    random_message = random.choice(messages)

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{page_title}</title>
    <style>
        body {{
            margin: 0; padding: 0; background-color: #0B0E14;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            display: flex; flex-direction: column;
            justify-content: center; align-items: center;
            min-height: 100vh; text-align: center;
        }}
        .message {{ color: #F1F5F9; font-weight: bold; font-size: 42px;
                   margin-bottom: 20px; max-width: 80%; line-height: 1.2; }}
        .subtitle {{ color: #64748B; font-size: 18px; margin-bottom: 40px; }}
        .button {{ background-color: {button_color}; color: white; border: none;
                   padding: 12px 24px; font-size: 18px; border-radius: 8px;
                   cursor: pointer; margin-bottom: 20px; }}
        .button:hover {{ opacity: 0.9; }}
        .footer {{ color: #64748B; font-size: 14px; }}
    </style>
</head>
<body>
    <div class="message">{random_message}</div>
    <div class="subtitle">{page_title}</div>
    <button class="button" onclick="window.location.reload()">Show me another</button>
    <div class="footer">askarchie.io</div>
</body>
</html>'''

    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "text/html; charset=utf-8",
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
        "body": html,
    }
"""


def _build_handler_zip() -> pulumi.Asset:
    """Build an in-memory zip with lambda_function.py — no /tmp file."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("lambda_function.py", HANDLER_SRC)
    return pulumi.StringAsset(base64.b64encode(buf.getvalue()).decode())


# ── CloudWatch Log Group ──────────────────────────────────────────────────
log_group = aws.cloudwatch.LogGroup(
    f"{project_name}-{environment}-lambda-logs",
    name=f"/aws/lambda/{project_name}-{environment}-function",
    retention_in_days=log_retention_days,
    tags=common_tags,
)

# ── IAM Role ──────────────────────────────────────────────────────────────
lambda_role = aws.iam.Role(
    f"{project_name}-{environment}-lambda-role",
    name=f"{project_name}-{environment}-lambda-role",
    assume_role_policy=json.dumps({
        "Version": "2012-10-17",
        "Statement": [{
            "Action": "sts:AssumeRole",
            "Effect": "Allow",
            "Principal": {"Service": "lambda.amazonaws.com"},
        }],
    }),
    tags=common_tags,
)

# Basic execution policy
basic_attach = aws.iam.RolePolicyAttachment(
    f"{project_name}-{environment}-lambda-basic",
    role=lambda_role.name,
    policy_arn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
)

# X-Ray attachment (conditional) — +1 resource for Prod
xray_attach = None
if enable_xray:
    xray_attach = aws.iam.RolePolicyAttachment(
        f"{project_name}-{environment}-lambda-xray",
        role=lambda_role.name,
        policy_arn="arn:aws:iam::aws:policy/AWSXRayDaemonWriteAccess",
    )

# SQS DLQ (conditional) — +1 resource for Prod
dlq = None
dlq_policy = None
if enable_dlq:
    dlq = aws.sqs.Queue(
        f"{project_name}-{environment}-dlq",
        name=f"{project_name}-{environment}-dlq",
        tags=common_tags,
    )
    dlq_policy = aws.iam.RolePolicy(
        f"{project_name}-{environment}-lambda-dlq-policy",
        name=f"{project_name}-{environment}-lambda-dlq-policy",
        role=lambda_role.id,
        policy=dlq.arn.apply(lambda arn: json.dumps({
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Action": ["sqs:SendMessage", "sqs:GetQueueAttributes"],
                "Resource": arn,
            }],
        })),
    )

# ── Lambda Function ───────────────────────────────────────────────────────
function = aws.lambda_.Function(
    f"{project_name}-{environment}-function",
    name=f"{project_name}-{environment}-function",
    role=lambda_role.arn,
    handler="lambda_function.lambda_handler",
    runtime="python3.12",
    memory_size=lambda_memory,
    timeout=lambda_timeout,
    reserved_concurrent_executions=reserved_concurrency if reserved_concurrency > 0 else None,
    code=pulumi.AssetArchive({
        "lambda_function.py": pulumi.StringAsset(HANDLER_SRC),
    }),
    environment=aws.lambda_.FunctionEnvironmentArgs(
        variables={
            "PAGE_TITLE": page_title,
            "BUTTON_COLOR": button_color,
        },
    ),
    # Explicit log group binding so retention sticks + destroy doesn't orphan
    logging_config=aws.lambda_.FunctionLoggingConfigArgs(
        log_format="Text",
        log_group=log_group.name,
    ),
    dead_letter_config=(
        aws.lambda_.FunctionDeadLetterConfigArgs(target_arn=dlq.arn)
        if enable_dlq and dlq is not None
        else None
    ),
    tracing_config=(
        aws.lambda_.FunctionTracingConfigArgs(mode="Active")
        if enable_xray else None
    ),
    tags=common_tags,
    opts=pulumi.ResourceOptions(depends_on=[log_group]),
)

# ── Function URL ──────────────────────────────────────────────────────────
function_url = aws.lambda_.FunctionUrl(
    f"{project_name}-{environment}-function-url",
    function_name=function.name,
    authorization_type="NONE",
    cors=aws.lambda_.FunctionUrlCorsArgs(
        allow_credentials=False,
        allow_origins=["*"],
        allow_methods=["GET"],
        allow_headers=["date", "keep-alive"],
        expose_headers=["date", "keep-alive"],
        max_age=86400,
    ),
)

# Permissions (both required for public Function URL access)
url_permission = aws.lambda_.Permission(
    f"{project_name}-{environment}-fn-url-perm",
    statement_id="FunctionURLAllowPublicAccess",
    action="lambda:InvokeFunctionUrl",
    function=function.name,
    principal="*",
    function_url_auth_type="NONE",
)

invoke_permission = aws.lambda_.Permission(
    f"{project_name}-{environment}-fn-invoke-perm",
    statement_id="AllowFunctionUrlInvoke",
    action="lambda:InvokeFunction",
    function=function.name,
    principal="*",
)

# ── Outputs ───────────────────────────────────────────────────────────────
pulumi.export("function_url", function_url.function_url)
pulumi.export("function_arn", function.arn)
pulumi.export("function_name", function.name)
pulumi.export("log_group_name", log_group.name)
pulumi.export("role_arn", lambda_role.arn)
if dlq is not None:
    pulumi.export("dlq_arn", dlq.arn)
