# -----------------------------------------------------------------------------
# Outputs
# -----------------------------------------------------------------------------

output "location" {
  description = "Azure location this stack deployed into. Governance pins this to the approved location via the location locked-field; the value echoes what was actually applied."
  value       = azurerm_resource_group.main.location
}

output "resource_group" {
  description = "Platform resource group name."
  value       = azurerm_resource_group.main.name
}

output "vnet_id" {
  description = "Platform virtual network id."
  value       = azurerm_virtual_network.main.id
}

output "assets_storage_account" {
  description = "Assets storage account name."
  value       = azurerm_storage_account.assets.name
}

output "log_analytics_workspace_id" {
  description = "Log Analytics workspace id."
  value       = azurerm_log_analytics_workspace.app.id
}

output "app_identity_principal_id" {
  description = "Application user-assigned identity principal id."
  value       = azurerm_user_assigned_identity.app.principal_id
}
