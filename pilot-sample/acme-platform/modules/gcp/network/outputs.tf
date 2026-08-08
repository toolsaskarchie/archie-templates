output "network_id" { description = "VPC id."     value = google_compute_network.main.id }
output "subnet_id"  { description = "Subnet id."  value = google_compute_subnetwork.private.id }
