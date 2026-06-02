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
import re

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
    connection so it's evaluated at apply time."""
    storage_connection_string, ai_cs, ai_k = args[0], args[1], args[2]
    settings = [
        az.web.NameValuePairArgs(name="AzureWebJobsStorage", value=storage_connection_string),
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
