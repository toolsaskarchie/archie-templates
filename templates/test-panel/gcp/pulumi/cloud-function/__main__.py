"""
─── Test Panel: GCP Cloud Function (Pulumi) ─────────────────────────────────
Mirror of #1 AWS Lambda. Same rotating HTML landing page.

Resources per profile:
  Non-prod:  4  (bucket, source-archive, function-v2, IAM-binding)
  Prod:      6  (+ VPC connector + connector IAM-binding = +2)

Drift-injectable fields:
  service_config.available_memory   → gcloud functions deploy --memory
  service_config.timeout_seconds    → gcloud functions deploy --timeout
  service_config.environment_variables.PAGE_TITLE → gcloud functions deploy --set-env-vars
  bucket lifecycle_rule             → gsutil lifecycle set / gcloud storage buckets update
"""
import json
import os
import tempfile
import zipfile

import pulumi
import pulumi_gcp as gcp

config = pulumi.Config()
gcp_config = pulumi.Config("gcp")


def cfg(key: str, fallback=None):
    try:
        return config.get(key) or fallback
    except Exception:
        return fallback


# ── Config ────────────────────────────────────────────────────────────────
project_name = cfg("project_name", "myapp")
environment = cfg("environment", "dev")
region = cfg("region") or gcp_config.get("region") or "us-central1"
gcp_project = cfg("gcp_project") or gcp_config.require("project")
memory = cfg("memory", "256M")
timeout_seconds = int(cfg("timeout_seconds", 30))
runtime = cfg("runtime", "python311")
enable_vpc_connector = str(cfg("enable_vpc_connector", "false")).lower() == "true"
page_title = cfg("page_title", "AskArchie — Cloud Standards Platform")
button_color = cfg("button_color", "#3B82F6")

base_name = f"{project_name}-{environment}"

common_labels = {
    "project": project_name.lower(),
    "environment": environment.lower(),
    "managedby": "archie",
}

# ── Handler source (same HTML as #1/#2/#3/#4) ─────────────────────────────
HANDLER_SRC = '''
import functions_framework
import os
import random


@functions_framework.http
def main(request):
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
    msg = random.choice(messages)
    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>{page_title}</title><style>
body{{margin:0;background:#0B0E14;font-family:-apple-system,sans-serif;
display:flex;flex-direction:column;justify-content:center;align-items:center;
min-height:100vh;text-align:center}}
.m{{color:#F1F5F9;font-weight:bold;font-size:42px;margin-bottom:20px;max-width:80%}}
.s{{color:#64748B;font-size:18px;margin-bottom:40px}}
.b{{background:{button_color};color:white;border:0;padding:12px 24px;
font-size:18px;border-radius:8px;cursor:pointer}}
.f{{color:#64748B;font-size:14px;margin-top:20px}}
</style></head><body>
<div class="m">{msg}</div><div class="s">{page_title}</div>
<button class="b" onclick="window.location.reload()">Show me another</button>
<div class="f">askarchie.io</div>
</body></html>"""
    return (html, 200, {"Content-Type": "text/html; charset=utf-8",
                        "Cache-Control": "no-cache, no-store, must-revalidate"})
'''

REQUIREMENTS_SRC = "functions-framework==3.*\n"


def _build_source_zip() -> str:
    """Write the handler+requirements to a temp zip on disk; return path."""
    fd, path = tempfile.mkstemp(suffix=".zip", prefix="cf-source-")
    os.close(fd)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("main.py", HANDLER_SRC)
        zf.writestr("requirements.txt", REQUIREMENTS_SRC)
    return path


# ── Source bucket ─────────────────────────────────────────────────────────
# Bucket name must be globally unique. Use project + name + env + region.
bucket_name = f"{gcp_project}-{base_name}-source"[:63].lower()
source_bucket = gcp.storage.Bucket(
    bucket_name,
    name=bucket_name,
    location=region.upper().split("-")[0],  # e.g. us-central1 → US
    uniform_bucket_level_access=True,
    force_destroy=True,
    labels=common_labels,
)

# Upload handler zip
source_zip_path = _build_source_zip()
source_object = gcp.storage.BucketObject(
    f"{base_name}-source-archive",
    bucket=source_bucket.name,
    name="source.zip",
    source=pulumi.FileAsset(source_zip_path),
)

# ── VPC Connector (conditional, Prod-only) ────────────────────────────────
# Requires a /28 subnet range that doesn't overlap existing subnets. Static
# 10.8.0.0/28 — Prod profile callers can override if it collides.
connector = None
connector_iam = None
if enable_vpc_connector:
    connector = gcp.vpcaccess.Connector(
        f"{base_name}-vpc-conn",
        name=f"{base_name[:18]}-conn"[:25],  # connector names capped at 25 chars
        region=region,
        ip_cidr_range="10.8.0.0/28",
        network="default",
        min_throughput=200,
        max_throughput=300,
    )

# ── Cloud Function (Gen 2) ────────────────────────────────────────────────
function = gcp.cloudfunctionsv2.Function(
    f"{base_name}-fn",
    name=f"{base_name}-fn",
    location=region,
    description=f"Archie test-panel landing page ({environment})",
    build_config=gcp.cloudfunctionsv2.FunctionBuildConfigArgs(
        runtime=runtime,
        entry_point="main",
        source=gcp.cloudfunctionsv2.FunctionBuildConfigSourceArgs(
            storage_source=gcp.cloudfunctionsv2.FunctionBuildConfigSourceStorageSourceArgs(
                bucket=source_bucket.name,
                object=source_object.name,
            ),
        ),
    ),
    service_config=gcp.cloudfunctionsv2.FunctionServiceConfigArgs(
        max_instance_count=10,
        min_instance_count=0,
        available_memory=memory,
        timeout_seconds=timeout_seconds,
        ingress_settings="ALLOW_ALL",
        environment_variables={
            "PAGE_TITLE": page_title,
            "BUTTON_COLOR": button_color,
        },
        vpc_connector=connector.id if connector is not None else None,
        vpc_connector_egress_settings="PRIVATE_RANGES_ONLY" if connector is not None else None,
    ),
    labels=common_labels,
)

# Allow unauthenticated invocation
invoker_binding = gcp.cloudrunv2.ServiceIamMember(
    f"{base_name}-fn-invoker",
    project=gcp_project,
    location=region,
    name=function.name,
    role="roles/run.invoker",
    member="allUsers",
)

# If VPC connector enabled, grant function's runtime SA access to use it
if connector is not None:
    connector_iam = gcp.projects.IAMMember(
        f"{base_name}-conn-user",
        project=gcp_project,
        role="roles/vpcaccess.user",
        member=function.service_config.apply(
            lambda sc: f"serviceAccount:{sc.service_account_email}"
            if sc and sc.service_account_email else "serviceAccount:unknown@example.gserviceaccount.com"
        ),
    )

# ── Outputs ───────────────────────────────────────────────────────────────
pulumi.export("function_url", function.service_config.apply(lambda sc: sc.uri if sc else ""))
pulumi.export("function_name", function.name)
pulumi.export("source_bucket", source_bucket.name)
pulumi.export("region", region)
if connector is not None:
    pulumi.export("vpc_connector_id", connector.id)
