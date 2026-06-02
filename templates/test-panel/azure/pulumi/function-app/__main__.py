"""
─── Test Panel: Azure Function App (Pulumi) ─────────────────────────────────
Pulumi mirror of #3 (templates/test-panel/azure/terraform/function-app).
Same resources, same conditional gates, same rotating HTML landing page.

Resources per profile:
  Non-prod:  5  (RG, storage, plan, function app, web-config-source-control)
  Prod:      7  (+ App Insights component + staging-slot marker container)

QUOTA STRATEGY:
  - Consumption plan (Y1) — no VM quota
  - LRS storage           — no cost concern
  - No LBs, no Premium    — sandbox-safe

Drift-injectable fields:
  app_settings.PAGE_TITLE     → az functionapp config appsettings set
  app_settings.BUTTON_COLOR   → az functionapp config appsettings set
  site_config.python_version  → az functionapp config set --linux-fx-version
  storage_account SKU         → az storage account update --sku
"""
import base64
import io
import os
import re
import tempfile
import zipfile

import pulumi
import pulumi_azure_native as az

config = pulumi.Config()


def cfg(key: str, fallback=None):
    try:
        return config.get(key) or fallback
    except Exception:
        return fallback


# ── Config ────────────────────────────────────────────────────────────────
project_name = cfg("project_name", "myapp")
environment = cfg("environment", "dev")
location = cfg("location", "eastus")
runtime_version = cfg("runtime_version", "3.11")
enable_app_insights = str(cfg("enable_app_insights", "false")).lower() == "true"
enable_slot = str(cfg("enable_slot", "false")).lower() == "true"
page_title = cfg("page_title", "AskArchie — Cloud Standards Platform")
button_color = cfg("button_color", "#3B82F6")

base_name = f"{project_name}-{environment}"
storage_name = re.sub(r"[^a-z0-9]", "", f"{project_name}{environment}sa".lower())[:24]

common_tags = {
    "Project": project_name,
    "Environment": environment,
    "ManagedBy": "Archie",
}

# ── Handler source (identical demo HTML to #1/#2/#3/#5) ────────────────────
HANDLER_PY = '''import os
import random
import azure.functions as func


def main(req: func.HttpRequest) -> func.HttpResponse:
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
        "Describe. Generate. Govern. Deploy."
    ]

    page_title = os.environ.get("PAGE_TITLE", "AskArchie")
    button_color = os.environ.get("BUTTON_COLOR", "#3B82F6")
    random_message = random.choice(messages)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{page_title}</title>
    <style>
        body {{
            margin: 0;
            padding: 0;
            background-color: #0B0E14;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            text-align: center;
        }}
        .message {{
            color: #F1F5F9;
            font-weight: bold;
            font-size: 42px;
            margin-bottom: 20px;
            max-width: 80%;
            line-height: 1.2;
        }}
        .subtitle {{
            color: #64748B;
            font-size: 18px;
            margin-bottom: 40px;
        }}
        .button {{
            background-color: {button_color};
            color: white;
            border: none;
            padding: 12px 24px;
            font-size: 18px;
            border-radius: 8px;
            cursor: pointer;
            margin-bottom: 20px;
        }}
        .button:hover {{
            opacity: 0.9;
        }}
        .footer {{
            color: #64748B;
            font-size: 14px;
        }}
    </style>
</head>
<body>
    <div class="message">{random_message}</div>
    <div class="subtitle">{page_title}</div>
    <button class="button" onclick="window.location.reload()">Show me another</button>
    <div class="footer">askarchie.io</div>
</body>
</html>"""

    return func.HttpResponse(
        html_content,
        mimetype="text/html",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )
'''

FUNCTION_JSON = '''{
    "scriptFile": "__init__.py",
    "bindings": [
        {
            "authLevel": "anonymous",
            "type": "httpTrigger",
            "direction": "in",
            "name": "req",
            "methods": ["get"],
            "route": "http_landing"
        },
        {
            "type": "http",
            "direction": "out",
            "name": "$return"
        }
    ]
}
'''

HOST_JSON = '''{
    "version": "2.0",
    "extensionBundle": {
        "id": "Microsoft.Azure.Functions.ExtensionBundle",
        "version": "[4.*, 5.0.0)"
    }
}
'''


def _build_handler_zip() -> str:
    """Build the deployment zip on disk; return path. Layout:
        /__init__.py          ← package marker (empty)
        /host.json
        /requirements.txt
        /http_landing/__init__.py     ← handler
        /http_landing/function.json   ← binding config
    """
    fd, path = tempfile.mkstemp(suffix=".zip", prefix="azfn-source-")
    os.close(fd)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("host.json", HOST_JSON)
        zf.writestr("requirements.txt", "azure-functions\n")
        zf.writestr("http_landing/__init__.py", HANDLER_PY)
        zf.writestr("http_landing/function.json", FUNCTION_JSON)
    return path


# ── Resource Group ────────────────────────────────────────────────────────
rg = az.resources.ResourceGroup(
    f"{base_name}-rg",
    resource_group_name=f"{base_name}-rg",
    location=location,
    tags=common_tags,
)

# ── Storage Account ───────────────────────────────────────────────────────
storage = az.storage.StorageAccount(
    storage_name,
    account_name=storage_name,
    resource_group_name=rg.name,
    location=rg.location,
    sku=az.storage.SkuArgs(name="Standard_LRS"),
    kind="StorageV2",
    minimum_tls_version="TLS1_2",
    tags=common_tags,
)

# Get primary connection string for the function app
storage_keys = az.storage.list_storage_account_keys_output(
    resource_group_name=rg.name,
    account_name=storage.name,
)
storage_conn = pulumi.Output.all(storage.name, storage_keys.keys).apply(
    lambda args: f"DefaultEndpointsProtocol=https;AccountName={args[0]};"
                 f"AccountKey={args[1][0]['value']};EndpointSuffix=core.windows.net"
)

# Source-package container + handler zip → wire via WEBSITE_RUN_FROM_PACKAGE
source_container = az.storage.BlobContainer(
    f"{base_name}-source-container",
    account_name=storage.name,
    resource_group_name=rg.name,
    container_name="source",
    public_access=az.storage.PublicAccess.NONE,
)

_handler_zip_path = _build_handler_zip()
source_blob = az.storage.Blob(
    f"{base_name}-source-blob",
    blob_name="handler.zip",
    container_name=source_container.name,
    account_name=storage.name,
    resource_group_name=rg.name,
    type=az.storage.BlobType.BLOCK,
    source=pulumi.FileAsset(_handler_zip_path),
)

# Build a SAS URL the Function App can read at runtime
source_sas = az.storage.list_storage_account_service_sas_output(
    account_name=storage.name,
    resource_group_name=rg.name,
    canonicalized_resource=pulumi.Output.concat("/blob/", storage.name, "/source"),
    resource=az.storage.SignedResource.C,
    permissions=az.storage.Permissions.R,
    shared_access_expiry_time="2030-12-31T23:59:59Z",
    protocols=az.storage.HttpProtocol.HTTPS,
)
package_url = pulumi.Output.all(storage.name, source_sas.service_sas_token).apply(
    lambda args: f"https://{args[0]}.blob.core.windows.net/source/handler.zip?{args[1]}"
)

# ── Service Plan (Consumption) ────────────────────────────────────────────
plan = az.web.AppServicePlan(
    f"{base_name}-plan",
    name=f"{base_name}-plan",
    resource_group_name=rg.name,
    location=rg.location,
    sku=az.web.SkuDescriptionArgs(name="Y1", tier="Dynamic"),
    reserved=True,  # Linux
    tags=common_tags,
)

# ── App Insights (conditional, Prod-only) ─────────────────────────────────
app_insights = None
ai_conn_string = None
ai_key = None
if enable_app_insights:
    app_insights = az.insights.Component(
        f"{base_name}-ai",
        resource_name_=f"{base_name}-ai",
        resource_group_name=rg.name,
        location=rg.location,
        kind="web",
        application_type=az.insights.ApplicationType.WEB,
        retention_in_days=90,
        tags=common_tags,
    )
    ai_conn_string = app_insights.connection_string
    ai_key = app_insights.instrumentation_key

# ── Function App ──────────────────────────────────────────────────────────
def _build_app_settings(args):
    """Returns list of NameValuePair for the Function App. Wraps the storage
    connection + the package URL so they're evaluated at apply time."""
    storage_connection_string, ai_cs, ai_k, pkg_url = args[0], args[1], args[2], args[3]
    settings = [
        az.web.NameValuePairArgs(name="AzureWebJobsStorage", value=storage_connection_string),
        az.web.NameValuePairArgs(name="WEBSITE_RUN_FROM_PACKAGE", value=pkg_url),
        az.web.NameValuePairArgs(name="WEBSITE_CONTENTAZUREFILECONNECTIONSTRING",
                                  value=storage_connection_string),
        az.web.NameValuePairArgs(name="WEBSITE_CONTENTSHARE", value=f"{base_name}-content"),
        az.web.NameValuePairArgs(name="FUNCTIONS_EXTENSION_VERSION", value="~4"),
        az.web.NameValuePairArgs(name="FUNCTIONS_WORKER_RUNTIME", value="python"),
        az.web.NameValuePairArgs(name="PAGE_TITLE", value=page_title),
        az.web.NameValuePairArgs(name="BUTTON_COLOR", value=button_color),
    ]
    if ai_cs:
        settings.append(az.web.NameValuePairArgs(
            name="APPLICATIONINSIGHTS_CONNECTION_STRING", value=ai_cs,
        ))
    if ai_k:
        settings.append(az.web.NameValuePairArgs(
            name="APPINSIGHTS_INSTRUMENTATIONKEY", value=ai_k,
        ))
    return settings


app_settings_output = pulumi.Output.all(
    storage_conn,
    ai_conn_string if ai_conn_string else pulumi.Output.from_input(None),
    ai_key if ai_key else pulumi.Output.from_input(None),
    package_url,
).apply(_build_app_settings)

function_app = az.web.WebApp(
    f"{base_name}-fn",
    name=f"{base_name}-fn",
    resource_group_name=rg.name,
    location=rg.location,
    server_farm_id=plan.id,
    kind="functionapp,linux",
    reserved=True,
    site_config=az.web.SiteConfigArgs(
        linux_fx_version=f"Python|{runtime_version}",
        always_on=False,  # not supported on Y1
        app_settings=app_settings_output,
    ),
    https_only=True,
    tags=common_tags,
)

# ── Staging slot marker (conditional, Prod-only) ──────────────────────────
# Real Slot resources need Premium plan; we provision a Blob container so
# Prod = N+2 resources without quota cost. Standard pattern for the
# Consumption-plan profile of this blueprint.
slot_marker = None
if enable_slot:
    slot_marker = az.storage.BlobContainer(
        f"{base_name}-slot-marker",
        account_name=storage.name,
        resource_group_name=rg.name,
        container_name="staging-slot-marker",
        public_access=az.storage.PublicAccess.NONE,
    )

# ── Outputs ───────────────────────────────────────────────────────────────
pulumi.export("function_url", pulumi.Output.concat(
    "https://", function_app.default_host_name, "/api/http_landing"
))
pulumi.export("function_app_name", function_app.name)
pulumi.export("function_app_id", function_app.id)
pulumi.export("resource_group_name", rg.name)
pulumi.export("storage_account_name", storage.name)
if app_insights is not None:
    pulumi.export("app_insights_id", app_insights.id)
