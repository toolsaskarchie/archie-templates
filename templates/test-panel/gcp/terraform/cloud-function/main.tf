# ─── Test Panel: GCP Cloud Function HTTP (TF, Gen 2) ─────────────────────────
# TF mirror of #5 (gcp/pulumi/cloud-function). Same resources, same conditional
# gates, same rotating HTML landing page as #1/#2/#3/#4.
#
# Resources per profile:
#   Non-prod:  4  (source bucket, source object, function v2, run-IAM-binding)
#   Prod:      6  (+ VPC connector + connector IAM-binding = +2)
#
# Drift-injectable fields:
#   | Field                       | Inject CLI                                                                  | Verify CLI                                  |
#   |-----------------------------|------------------------------------------------------------------------------|---------------------------------------------|
#   | service_config memory       | gcloud functions deploy FN --memory=512MB                                    | gcloud functions describe FN                |
#   | service_config timeout      | gcloud functions deploy FN --timeout=60s                                     | gcloud functions describe FN                |
#   | env PAGE_TITLE              | gcloud functions deploy FN --update-env-vars PAGE_TITLE=Drifted              | gcloud functions describe FN                |
#   | bucket lifecycle            | gsutil lifecycle set lifecycle.json gs://BUCKET                              | gsutil lifecycle get gs://BUCKET            |
#
# Drift noise (do NOT inject — known false positives):
#   - service_config.uri          (computed at deploy time)
#   - generation/metageneration   (object versioning bookkeeping)

locals {
  base_name = "${var.project_name}-${var.environment}"
  # Bucket names: globally unique, lowercase, max 63 chars
  bucket_name = lower(substr("${var.gcp_project}-${local.base_name}-source", 0, 63))

  common_labels = merge(
    {
      project     = lower(var.project_name)
      environment = lower(var.environment)
      managedby   = "archie"
    },
    var.labels,
  )

  # Inline handler — IDENTICAL look/feel to the other 5 panel blueprints.
  handler_py = <<-PYEOF
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

        return (
            html_content,
            200,
            {
                "Content-Type": "text/html; charset=utf-8",
                "Cache-Control": "no-cache, no-store, must-revalidate",
            },
        )
  PYEOF
}

# Source archive (handler + requirements packed together)
data "archive_file" "source_zip" {
  type        = "zip"
  output_path = "${path.module}/source.zip"
  source {
    filename = "main.py"
    content  = local.handler_py
  }
  source {
    filename = "requirements.txt"
    content  = "functions-framework==3.*\n"
  }
}

# Source code bucket
resource "google_storage_bucket" "source" {
  name                        = local.bucket_name
  location                    = upper(substr(var.region, 0, 2))  # us-central1 → US
  uniform_bucket_level_access = true
  force_destroy               = true
  labels                      = local.common_labels
}

# Source code object
resource "google_storage_bucket_object" "source_archive" {
  name   = "source-${data.archive_file.source_zip.output_md5}.zip"
  bucket = google_storage_bucket.source.name
  source = data.archive_file.source_zip.output_path
}

# Serverless VPC Connector (conditional, Prod-only)
resource "google_vpc_access_connector" "connector" {
  count          = var.enable_vpc_connector ? 1 : 0
  name           = substr("${local.base_name}-conn", 0, 25)  # connector names capped at 25
  region         = var.region
  network        = "default"
  ip_cidr_range  = "10.8.0.0/28"
  min_throughput = 200
  max_throughput = 300
}

# Cloud Function (Gen 2)
resource "google_cloudfunctions2_function" "main" {
  name        = "${local.base_name}-fn"
  location    = var.region
  description = "Archie test-panel landing page (${var.environment})"
  labels      = local.common_labels

  build_config {
    runtime     = var.runtime
    entry_point = "main"
    source {
      storage_source {
        bucket = google_storage_bucket.source.name
        object = google_storage_bucket_object.source_archive.name
      }
    }
  }

  service_config {
    max_instance_count = 10
    min_instance_count = 0
    available_memory   = var.memory
    timeout_seconds    = var.timeout_seconds
    ingress_settings   = "ALLOW_ALL"
    environment_variables = {
      PAGE_TITLE   = var.page_title
      BUTTON_COLOR = var.button_color
    }

    vpc_connector                 = var.enable_vpc_connector ? google_vpc_access_connector.connector[0].id : null
    vpc_connector_egress_settings = var.enable_vpc_connector ? "PRIVATE_RANGES_ONLY" : null
  }
}

# Allow unauthenticated invocation (function runs on Cloud Run under the hood)
resource "google_cloud_run_v2_service_iam_member" "invoker" {
  project  = var.gcp_project
  location = google_cloudfunctions2_function.main.location
  name     = google_cloudfunctions2_function.main.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# When VPC connector enabled, grant function's runtime SA access
resource "google_project_iam_member" "connector_user" {
  count   = var.enable_vpc_connector ? 1 : 0
  project = var.gcp_project
  role    = "roles/vpcaccess.user"
  member  = "serviceAccount:${google_cloudfunctions2_function.main.service_config[0].service_account_email}"
}
