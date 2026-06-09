output "network_id" {
  description = "Full GCP resource ID of the VPC network."
  value       = google_compute_network.main.id
}

output "network_name" {
  description = "Name of the VPC network."
  value       = google_compute_network.main.name
}

output "network_self_link" {
  description = "Self link URL of the VPC network."
  value       = google_compute_network.main.self_link
}

output "subnet_ids" {
  description = "List of subnet resource IDs."
  value       = google_compute_subnetwork.main[*].id
}

output "subnet_self_links" {
  description = "List of subnet self link URLs."
  value       = google_compute_subnetwork.main[*].self_link
}

output "routing_mode" {
  description = "Configured dynamic routing mode of the VPC."
  value       = google_compute_network.main.routing_mode
}
