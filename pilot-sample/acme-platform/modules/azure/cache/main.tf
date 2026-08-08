resource "azurerm_redis_cache" "main" {
  name                          = "${var.project}-${var.environment}-redis"
  location                      = var.location
  resource_group_name           = var.resource_group_name
  sku_name                      = var.sku_name
  family                        = var.sku_name == "Premium" ? "P" : "C"
  capacity                      = var.capacity
  minimum_tls_version           = "1.2"
  public_network_access_enabled = false
  tags                          = var.tags
}
