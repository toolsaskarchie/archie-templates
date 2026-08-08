resource "google_redis_instance" "main" {
  name                    = "${var.project}-${var.environment}-redis"
  project                 = var.project_id
  region                  = var.region
  tier                    = var.tier
  memory_size_gb          = var.memory_size_gb
  authorized_network      = var.network_id
  connect_mode            = "PRIVATE_SERVICE_ACCESS"
  auth_enabled            = true
  transit_encryption_mode = "SERVER_AUTHENTICATION"
  redis_version           = "REDIS_7_2"
  labels                  = var.labels
}
