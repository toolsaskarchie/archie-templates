resource "azurerm_kubernetes_cluster" "main" {
  name                      = "${var.project}-${var.environment}-aks"
  location                  = var.location
  resource_group_name       = var.resource_group_name
  dns_prefix                = "${var.project}-${var.environment}"
  kubernetes_version        = var.kubernetes_version
  local_account_disabled    = true
  role_based_access_control_enabled = true
  automatic_channel_upgrade = "patch"

  default_node_pool {
    name                = "system"
    vm_size             = var.node_vm_size
    vnet_subnet_id      = var.subnet_id
    enable_auto_scaling = true
    min_count           = var.node_min_count
    max_count           = var.node_max_count
    only_critical_addons_enabled = true
  }

  identity { type = "SystemAssigned" }

  network_profile {
    network_plugin = "azure"
    network_policy = "calico"
  }

  azure_active_directory_role_based_access_control {
    managed                = true
    azure_rbac_enabled     = true
  }

  tags = var.tags
}
