# -----------------------------------------------------------------------------
# Outputs
# -----------------------------------------------------------------------------

output "region" {
  description = "GCP region this stack deployed into. Governance pins this to the approved region via the region locked-field; the value echoes what was actually applied."
  value       = var.region
}

output "network_self_link" {
  description = "Platform VPC self link."
  value       = google_compute_network.vpc.self_link
}

output "subnet_self_link" {
  description = "Application subnet self link."
  value       = google_compute_subnetwork.app.self_link
}

output "assets_bucket" {
  description = "Assets GCS bucket name."
  value       = google_storage_bucket.assets.name
}

output "events_topic" {
  description = "Pub/Sub events topic id."
  value       = google_pubsub_topic.events.id
}

output "app_service_account_email" {
  description = "Least-privilege application service account email."
  value       = google_service_account.app.email
}
