output "function_url" {
  description = "Public HTTPS URL of the Cloud Function (Cloud Run service URL)"
  value       = google_cloudfunctions2_function.main.service_config[0].uri
}

output "function_name" {
  value = google_cloudfunctions2_function.main.name
}

output "function_id" {
  value = google_cloudfunctions2_function.main.id
}

output "source_bucket" {
  value = google_storage_bucket.source.name
}

output "region" {
  value = var.region
}

output "vpc_connector_id" {
  description = "Serverless VPC connector ID (null when disabled)"
  value       = length(google_vpc_access_connector.connector) > 0 ? google_vpc_access_connector.connector[0].id : null
}
