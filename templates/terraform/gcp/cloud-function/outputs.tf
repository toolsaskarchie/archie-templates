output "function_id" {
  description = "Full GCP resource ID of the Cloud Function (projects/.../locations/.../functions/...)."
  value       = google_cloudfunctions2_function.main.id
}

output "function_name" {
  description = "Name of the Cloud Function."
  value       = google_cloudfunctions2_function.main.name
}

output "function_url" {
  description = "HTTPS URL of the function (service_config.uri)."
  value       = google_cloudfunctions2_function.main.service_config[0].uri
}

output "source_bucket_name" {
  description = "Name of the GCS bucket holding the source archive."
  value       = google_storage_bucket.source.name
}

# Governance-visible outputs - echo the EFFECTIVE config the function
# was deployed with. Surfaces profile differences in the stack drawer.

output "runtime" {
  description = "Runtime the function was built with."
  value       = var.runtime
}

output "memory_mb" {
  description = "Memory allocation in MB. Profile lever."
  value       = var.memory_mb
}

output "timeout_seconds" {
  description = "Execution timeout in seconds. Profile lever."
  value       = var.timeout_seconds
}

output "min_instances" {
  description = "Minimum warm instances (0 = scale to zero). Profile lever."
  value       = var.min_instances
}

output "max_instances" {
  description = "Maximum concurrent instances. Profile lever."
  value       = var.max_instances
}
