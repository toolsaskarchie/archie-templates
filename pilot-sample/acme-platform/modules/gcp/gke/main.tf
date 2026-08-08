resource "google_container_cluster" "main" {
  name                     = "${var.project}-${var.environment}-gke"
  project                  = var.project_id
  location                 = var.region
  network                  = var.network_id
  subnetwork               = var.subnet_id
  remove_default_node_pool = true
  initial_node_count       = 1
  deletion_protection      = var.environment == "prod"

  private_cluster_config {
    enable_private_nodes    = true
    enable_private_endpoint = false
    master_ipv4_cidr_block  = "172.16.0.0/28"
  }

  workload_identity_config { workload_pool = "${var.project_id}.svc.id.goog" }
  database_encryption      { state = "ENCRYPTED" }
  release_channel          { channel = "REGULAR" }

  resource_labels = var.labels
}

resource "google_container_node_pool" "main" {
  name     = "${var.project}-${var.environment}-np"
  project  = var.project_id
  location = var.region
  cluster  = google_container_cluster.main.name

  autoscaling {
    min_node_count = var.min_node_count
    max_node_count = var.max_node_count
  }

  node_config {
    machine_type    = var.machine_type
    disk_type       = "pd-balanced"
    shielded_instance_config { enable_secure_boot = true }
    workload_metadata_config { mode = "GKE_METADATA" }
    labels          = var.labels
  }

  management { auto_repair = true auto_upgrade = true }
}
