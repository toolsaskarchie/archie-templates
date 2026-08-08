resource "azurerm_postgresql_flexible_server" "main" {
  name                          = "${var.project}-${var.environment}-pg"
  location                      = var.location
  resource_group_name           = var.resource_group_name
  version                       = "16"
  sku_name                      = var.sku_name
  storage_mb                    = var.storage_mb
  backup_retention_days         = var.backup_retention_days
  geo_redundant_backup_enabled  = var.geo_redundant_backup
  public_network_access_enabled = false

  dynamic "high_availability" {
    for_each = var.high_availability ? [1] : []
    content { mode = "ZoneRedundant" }
  }

  tags = var.tags
}
