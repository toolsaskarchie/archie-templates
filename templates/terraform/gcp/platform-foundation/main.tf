# -----------------------------------------------------------------------------
# Shared naming + labels
# -----------------------------------------------------------------------------

locals {
  name = "${var.project_name}-${var.environment}"

  common_labels = merge({
    project     = var.project_name
    environment = var.environment
    managed_by  = "archie-terraform"
  }, var.labels)
}

resource "random_string" "suffix" {
  length  = 6
  upper   = false
  special = false
}

# -----------------------------------------------------------------------------
# Network — custom VPC + application subnet + firewall (governed corporate-CIDR
# ingress on 443; egress left to GCP defaults).
# -----------------------------------------------------------------------------

resource "google_compute_network" "vpc" {
  name                    = "${local.name}-vpc"
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "app" {
  name                     = "${local.name}-app-subnet"
  ip_cidr_range            = var.subnet_cidr
  region                   = var.region
  network                  = google_compute_network.vpc.id
  private_ip_google_access = true
}

resource "google_compute_firewall" "allow_https" {
  name      = "${local.name}-allow-https"
  network   = google_compute_network.vpc.name
  direction = "INGRESS"

  allow {
    protocol = "tcp"
    ports    = ["443"]
  }

  source_ranges = [var.allowed_ingress_cidr]
  target_tags   = ["${local.name}-app"]
}

# -----------------------------------------------------------------------------
# Storage — private, versioned assets bucket with uniform access + lifecycle.
# -----------------------------------------------------------------------------

resource "google_storage_bucket" "assets" {
  name                        = lower("${local.name}-assets-${random_string.suffix.result}")
  location                    = var.region
  force_destroy               = false
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"

  versioning {
    enabled = var.bucket_versioning_enabled
  }

  lifecycle_rule {
    condition {
      age = var.bucket_age_days
    }
    action {
      type = "Delete"
    }
  }

  labels = local.common_labels
}

# -----------------------------------------------------------------------------
# Messaging — Pub/Sub topic + subscription (governed retention).
# -----------------------------------------------------------------------------

resource "google_pubsub_topic" "events" {
  name   = "${local.name}-events"
  labels = local.common_labels
}

resource "google_pubsub_subscription" "events" {
  name                       = "${local.name}-events-sub"
  topic                      = google_pubsub_topic.events.id
  message_retention_duration = "${var.pubsub_retention_seconds}s"
  retain_acked_messages      = false
  labels                     = local.common_labels
}

# -----------------------------------------------------------------------------
# Identity — least-privilege service account scoped to this stack's bucket.
# -----------------------------------------------------------------------------

resource "google_service_account" "app" {
  account_id   = "${var.project_name}-${var.environment}-app"
  display_name = "${local.name} application service account"
}

resource "google_storage_bucket_iam_member" "app_object_admin" {
  bucket = google_storage_bucket.assets.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.app.email}"
}
