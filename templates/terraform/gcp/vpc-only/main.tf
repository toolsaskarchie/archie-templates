locals {
  # GCP network names must be RFC1035: lowercase, start with a letter,
  # dashes ok, max 63 chars. Derive a safe name from project_name.
  safe_name = substr(lower(replace(var.project_name, "_", "-")), 0, 50)

  common_labels = {
    project     = local.safe_name
    environment = var.environment
    managed_by  = "archie"
  }
}

resource "google_compute_network" "main" {
  name                            = "${local.safe_name}-vpc"
  description                     = "Archie-managed VPC for ${var.project_name} (${var.environment})"
  auto_create_subnetworks         = false
  routing_mode                    = var.routing_mode
  delete_default_routes_on_create = false
}

resource "google_compute_subnetwork" "main" {
  count         = var.subnet_count
  name          = "${local.safe_name}-subnet-${count.index}"
  region        = var.region
  network       = google_compute_network.main.id
  ip_cidr_range = cidrsubnet(var.vpc_cidr, 8, count.index + 1)

  private_ip_google_access = true
}
