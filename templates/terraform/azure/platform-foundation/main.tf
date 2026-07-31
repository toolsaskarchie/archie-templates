# -----------------------------------------------------------------------------
# Shared naming + tags
# -----------------------------------------------------------------------------

locals {
  name    = "${var.project_name}-${var.environment}"
  sa_base = substr(lower(replace("${var.project_name}${var.environment}", "-", "")), 0, 16)

  common_tags = merge({
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "archie-terraform"
  }, var.tags)
}

resource "random_string" "suffix" {
  length  = 6
  upper   = false
  special = false
}

# -----------------------------------------------------------------------------
# Resource group
# -----------------------------------------------------------------------------

resource "azurerm_resource_group" "main" {
  name     = "${local.name}-rg"
  location = var.location
  tags     = local.common_tags
}

# -----------------------------------------------------------------------------
# Network — VNet + application subnet + NSG (governed corporate-CIDR ingress).
# -----------------------------------------------------------------------------

resource "azurerm_virtual_network" "main" {
  name                = "${local.name}-vnet"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  address_space       = [var.address_space]
  tags                = local.common_tags
}

resource "azurerm_subnet" "app" {
  name                 = "${local.name}-app-subnet"
  resource_group_name  = azurerm_resource_group.main.name
  virtual_network_name = azurerm_virtual_network.main.name
  address_prefixes     = [var.subnet_prefix]
}

resource "azurerm_network_security_group" "app" {
  name                = "${local.name}-app-nsg"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name

  security_rule {
    name                       = "AllowHttpsFromCorp"
    priority                   = 100
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "443"
    source_address_prefix      = var.allowed_ingress_cidr
    destination_address_prefix = "*"
  }

  tags = local.common_tags
}

resource "azurerm_subnet_network_security_group_association" "app" {
  subnet_id                 = azurerm_subnet.app.id
  network_security_group_id = azurerm_network_security_group.app.id
}

# -----------------------------------------------------------------------------
# Storage — encrypted, versioned, private assets account + container.
# -----------------------------------------------------------------------------

resource "azurerm_storage_account" "assets" {
  name                            = "st${local.sa_base}${random_string.suffix.result}"
  resource_group_name             = azurerm_resource_group.main.name
  location                        = azurerm_resource_group.main.location
  account_tier                    = "Standard"
  account_replication_type        = "LRS"
  min_tls_version                 = var.storage_min_tls
  allow_nested_items_to_be_public = false

  blob_properties {
    versioning_enabled = var.blob_versioning_enabled
    delete_retention_policy {
      days = var.blob_retention_days
    }
  }

  tags = local.common_tags
}

resource "azurerm_storage_container" "assets" {
  name                  = "assets"
  storage_account_id    = azurerm_storage_account.assets.id
  container_access_type = "private"
}

# -----------------------------------------------------------------------------
# Observability + identity — Log Analytics workspace and a user-assigned
# managed identity for the application.
# -----------------------------------------------------------------------------

resource "azurerm_log_analytics_workspace" "app" {
  name                = "${local.name}-law"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  sku                 = "PerGB2018"
  retention_in_days   = var.log_retention_days
  tags                = local.common_tags
}

resource "azurerm_user_assigned_identity" "app" {
  name                = "${local.name}-id"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  tags                = local.common_tags
}

# NOTE: a Storage Blob Data Contributor role assignment for the app identity would
# go here, but granting roles needs Microsoft.Authorization/roleAssignments/write
# (Owner / User Access Administrator) — which the deploy service principal does not
# hold. Assign it out-of-band with a privileged identity.
