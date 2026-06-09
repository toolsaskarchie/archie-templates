locals {
  # GCS + Cloud Function names must be globally unique + RFC1035 safe.
  # Derive a lowercase, dash-only name from project_name capped at 50 chars
  # so we have headroom for suffixes.
  safe_name = substr(lower(replace(var.project_name, "_", "-")), 0, 50)

  common_labels = {
    project     = local.safe_name
    environment = var.environment
    managed_by  = "archie"
  }
}

# Bucket that holds the zipped source archive. Gen 2 Cloud Functions read
# their source from GCS, not from inline content.
resource "google_storage_bucket" "source" {
  name                        = "${local.safe_name}-${var.environment}-fn-src"
  location                    = var.region
  force_destroy               = true
  uniform_bucket_level_access = true
  labels                      = local.common_labels
}

# Zip the bundled source dir (main.py + requirements.txt) into a local
# archive. The output_md5 becomes part of the object name so a source
# change rotates the upload + triggers a new function revision.
data "archive_file" "source" {
  type        = "zip"
  source_dir  = "${path.module}/source"
  output_path = "/tmp/${local.safe_name}-${var.environment}-source.zip"
}

resource "google_storage_bucket_object" "source" {
  name   = "source-${data.archive_file.source.output_md5}.zip"
  bucket = google_storage_bucket.source.name
  source = data.archive_file.source.output_path
}

resource "google_cloudfunctions2_function" "main" {
  name        = "${local.safe_name}-${var.environment}-fn"
  location    = var.region
  description = "Archie-managed Cloud Function for ${var.project_name} (${var.environment})"

  build_config {
    runtime     = var.runtime
    entry_point = var.entry_point
    source {
      storage_source {
        bucket = google_storage_bucket.source.name
        object = google_storage_bucket_object.source.name
      }
    }
  }

  service_config {
    max_instance_count    = var.max_instances
    min_instance_count    = var.min_instances
    available_memory      = "${var.memory_mb}M"
    timeout_seconds       = var.timeout_seconds
    environment_variables = var.env_vars
    ingress_settings      = "ALLOW_ALL"
  }

  labels = local.common_labels
}
