output "cluster_name" {
  description = "GKE cluster name."
  value       = google_container_cluster.main.name
}
output "cluster_endpoint" {
  description = "API endpoint."
  value       = google_container_cluster.main.endpoint
}
