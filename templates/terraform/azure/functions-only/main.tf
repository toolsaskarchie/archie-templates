locals {
  common_tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "Archie"
  }

  # Storage account names must be globally unique, 3-24 lowercase alphanumeric.
  # Strip non-alphanumeric, lowercase, cap base at 20 chars, append a 4-char
  # md5-derived suffix for collision avoidance. Deterministic per project_name.
  storage_base   = substr(replace(lower(var.project_name), "/[^a-z0-9]/", ""), 0, 20)
  storage_suffix = substr(md5(var.project_name), 0, 4)
  storage_name   = "${local.storage_base}${local.storage_suffix}"
}

resource "azurerm_resource_group" "main" {
  name     = var.resource_group_name
  location = var.location
  tags     = local.common_tags
}

resource "azurerm_storage_account" "main" {
  name                     = local.storage_name
  resource_group_name      = azurerm_resource_group.main.name
  location                 = azurerm_resource_group.main.location
  account_tier             = var.storage_tier
  account_replication_type = var.storage_replication
  account_kind             = "StorageV2"
  min_tls_version          = "TLS1_2"
  tags                     = local.common_tags
}

resource "azurerm_service_plan" "main" {
  name                = "${var.project_name}-plan"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  os_type             = "Linux"
  sku_name            = "Y1"
  tags                = local.common_tags
}

resource "azurerm_application_insights" "main" {
  name                = "${var.project_name}-ai"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  application_type    = "web"
  tags                = local.common_tags
}

resource "azurerm_linux_function_app" "main" {
  name                       = "${var.project_name}-fn"
  resource_group_name        = azurerm_resource_group.main.name
  location                   = azurerm_resource_group.main.location
  service_plan_id            = azurerm_service_plan.main.id
  storage_account_name       = azurerm_storage_account.main.name
  storage_account_access_key = azurerm_storage_account.main.primary_access_key

  functions_extension_version = "~4"

  site_config {
    application_stack {
      python_version = var.python_version
    }
  }

  app_settings = merge(
    {
      APPINSIGHTS_INSTRUMENTATIONKEY = azurerm_application_insights.main.instrumentation_key
    },
    var.app_settings,
  )

  tags = local.common_tags
}
