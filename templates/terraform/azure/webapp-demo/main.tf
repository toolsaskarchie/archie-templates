locals {
  common_tags = merge(
    {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "archie"
    },
    var.tags,
  )

  # Project_name + environment normalize to a stable resource name root.
  # Azure App Service hostnames must be globally unique — caller can override
  # by setting project_name to a likely-unique slug.
  name_root = "${var.project_name}-${var.environment}"
  rg_name   = var.resource_group_name != "" ? var.resource_group_name : "${local.name_root}-rg"
}

# ── Resource group ────────────────────────────────────────────────────────

resource "azurerm_resource_group" "main" {
  name     = local.rg_name
  location = var.location
  tags     = local.common_tags
}

# ── App Service Plan (Linux) ──────────────────────────────────────────────

resource "azurerm_service_plan" "main" {
  name                = "${local.name_root}-plan"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  os_type             = "Linux"
  sku_name            = var.sku_name
  tags                = local.common_tags
}

# ── App code archive ──────────────────────────────────────────────────────
# Inline Flask app (mirrors the AWS Lambda demo HTML 1:1 so a cross-cloud
# demo shows the same page from Azure and AWS). PAGE_TITLE / BUTTON_COLOR
# are env-driven on both clouds so the same governance lock controls both.

resource "local_file" "app_py" {
  filename = "${path.module}/app/app.py"
  content  = <<-EOF
    import os
    import random
    from flask import Flask, Response

    app = Flask(__name__)

    MESSAGES = [
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

    @app.route("/")
    def index():
        page_title = os.environ.get("PAGE_TITLE", "AskArchie")
        button_color = os.environ.get("BUTTON_COLOR", "#3B82F6")
        random_message = random.choice(MESSAGES)
        html = f"""<!DOCTYPE html>
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
        return Response(html, mimetype="text/html; charset=utf-8", headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        })

    if __name__ == "__main__":
        # App Service sets PORT in the environment; default 8000 for local runs.
        app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
  EOF
}

resource "local_file" "requirements_txt" {
  filename = "${path.module}/app/requirements.txt"
  content  = "flask==3.0.3\ngunicorn==22.0.0\n"
}

data "archive_file" "app_zip" {
  type        = "zip"
  source_dir  = "${path.module}/app"
  output_path = "${path.module}/app.zip"
  depends_on  = [local_file.app_py, local_file.requirements_txt]
}

# ── Linux Web App ─────────────────────────────────────────────────────────

resource "azurerm_linux_web_app" "main" {
  name                = "${local.name_root}-app"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  service_plan_id     = azurerm_service_plan.main.id

  https_only      = var.https_only
  zip_deploy_file = data.archive_file.app_zip.output_path

  site_config {
    always_on = var.always_on
    # Trigger Oryx to install requirements.txt and pick gunicorn entrypoint.
    app_command_line = "gunicorn --bind=0.0.0.0:8000 --timeout 600 app:app"

    application_stack {
      python_version = var.python_version
    }
  }

  app_settings = {
    PAGE_TITLE                          = var.page_title
    BUTTON_COLOR                        = var.button_color
    SCM_DO_BUILD_DURING_DEPLOYMENT      = "true"
    WEBSITES_PORT                       = "8000"
    # Force re-deploy when archive contents change.
    WEBSITE_RUN_FROM_PACKAGE_HASH       = data.archive_file.app_zip.output_base64sha256
  }

  tags = local.common_tags
}
