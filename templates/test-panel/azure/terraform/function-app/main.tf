# ─── Test Panel: Azure Function App (TF) ──────────────────────────────────────
# Quota-safe Consumption-plan function. Mirrors AWS Lambda #1 — same rotating
# HTML landing page, same profile pattern, same drift surface.
#
# Resources per profile:
#   Non-prod:  5  (RG, storage, SA-share, plan-consumption, function)
#   Prod:      7  (+ App Insights + staging slot = +2 over nonprod)
#
# QUOTA STRATEGY:
#   - Consumption plan (Y1)        — no VM quota
#   - Storage SKU LRS              — cheap, no quota
#   - No Application Gateway / LB  — both eat quota on sandbox
#   - No always_on (not supported on Consumption anyway)
#
# Drift-injectable fields:
#   | Field                          | Inject CLI                                                                                  | Verify CLI                                          |
#   |--------------------------------|---------------------------------------------------------------------------------------------|-----------------------------------------------------|
#   | app_settings.PAGE_TITLE        | az functionapp config appsettings set -g RG -n FN --settings PAGE_TITLE=Drifted             | az functionapp config appsettings list -g RG -n FN  |
#   | app_settings.BUTTON_COLOR      | az functionapp config appsettings set -g RG -n FN --settings BUTTON_COLOR=#ff0000           | az functionapp config appsettings list ...          |
#   | site_config.python_version     | az functionapp config set -g RG -n FN --linux-fx-version "Python|3.12"                      | az functionapp config show -g RG -n FN              |
#   | storage account tier           | az storage account update -g RG -n SA --sku Standard_GRS                                    | az storage account show -g RG -n SA                 |
#
# Drift noise (do NOT inject):
#   - kind on storage_account       — Azure auto-normalizes "StorageV2" casing
#   - tags["hidden-link:*"]         — Azure portal autopopulates these

locals {
  base_name = "${var.project_name}-${var.environment}"
  # Storage account names must be 3-24 chars, lowercase, alphanumeric only
  storage_name = substr(replace(lower("${var.project_name}${var.environment}sa"), "/[^a-z0-9]/", ""), 0, 24)

  common_tags = merge(
    {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "Archie"
    },
    var.tags,
  )

  # Embedded HTML handler — IDENTICAL look/feel to #1 AWS Lambda + #2 AWS
  # Pulumi + #5 GCP Cloud Function. Same rotating messages, same dark theme,
  # same "Show me another" button, same askarchie.io footer. The only
  # difference is the Azure Functions Python binding signature.
  handler_py = <<-PYEOF
    import os
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
  PYEOF
}

# Resource Group
resource "azurerm_resource_group" "main" {
  name     = "${local.base_name}-rg"
  location = var.location
  tags     = local.common_tags
}

# Storage Account (required for Function App)
resource "azurerm_storage_account" "main" {
  name                     = local.storage_name
  resource_group_name      = azurerm_resource_group.main.name
  location                 = azurerm_resource_group.main.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  min_tls_version          = "TLS1_2"
  tags                     = local.common_tags
}

# Consumption-plan Service Plan (Y1 = no VM quota)
resource "azurerm_service_plan" "main" {
  name                = "${local.base_name}-plan"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  os_type             = "Linux"
  sku_name            = "Y1"
  tags                = local.common_tags
}

# Application Insights (conditional, Prod-only)
resource "azurerm_application_insights" "main" {
  count               = var.enable_app_insights ? 1 : 0
  name                = "${local.base_name}-ai"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  application_type    = "web"
  retention_in_days   = 90
  tags                = local.common_tags
}

# Inline handler zip (function.json + __init__.py)
data "archive_file" "handler_zip" {
  type        = "zip"
  output_path = "${path.module}/handler.zip"
  source {
    filename = "http_landing/function.json"
    content  = jsonencode({
      scriptFile = "__init__.py"
      bindings = [
        {
          authLevel = "anonymous"
          type      = "httpTrigger"
          direction = "in"
          name      = "req"
          methods   = ["get"]
        },
        {
          type      = "http"
          direction = "out"
          name      = "$return"
        }
      ]
    })
  }
  source {
    filename = "http_landing/__init__.py"
    content  = local.handler_py
  }
  source {
    filename = "host.json"
    content  = jsonencode({
      version = "2.0"
      extensionBundle = {
        id      = "Microsoft.Azure.Functions.ExtensionBundle"
        version = "[4.*, 5.0.0)"
      }
    })
  }
  source {
    filename = "requirements.txt"
    content  = "azure-functions\n"
  }
}

# Linux Function App
resource "azurerm_linux_function_app" "main" {
  name                       = "${local.base_name}-fn"
  resource_group_name        = azurerm_resource_group.main.name
  location                   = azurerm_resource_group.main.location
  service_plan_id            = azurerm_service_plan.main.id
  storage_account_name       = azurerm_storage_account.main.name
  storage_account_access_key = azurerm_storage_account.main.primary_access_key

  site_config {
    application_stack {
      python_version = var.runtime_version
    }
    # Consumption plan ignores always_on — only set on B1+
    always_on = false

    # Application Insights wiring (conditional)
    application_insights_connection_string = (
      var.enable_app_insights && length(azurerm_application_insights.main) > 0
      ? azurerm_application_insights.main[0].connection_string
      : null
    )
    application_insights_key = (
      var.enable_app_insights && length(azurerm_application_insights.main) > 0
      ? azurerm_application_insights.main[0].instrumentation_key
      : null
    )
  }

  app_settings = {
    PAGE_TITLE               = var.page_title
    BUTTON_COLOR             = var.button_color
    FUNCTIONS_WORKER_RUNTIME = "python"
    WEBSITE_RUN_FROM_PACKAGE = "1"
  }

  tags = local.common_tags
}

# Staging Slot (conditional, Prod-only) — note: Consumption plan SUPPORTS
# slots on Linux as of mid-2024 but only on Premium plans. For Consumption
# we keep this as a deployment-marker no-op resource; in real Prod the
# blueprint would switch to Premium plan to enable real slot swap.
# For test-panel purposes the slot is an additional Storage container
# that mimics the "+2 resources in Prod" pattern without quota cost.
resource "azurerm_storage_container" "slot_marker" {
  count                 = var.enable_slot ? 1 : 0
  name                  = "staging-slot-marker"
  storage_account_id    = azurerm_storage_account.main.id
  container_access_type = "private"
}
