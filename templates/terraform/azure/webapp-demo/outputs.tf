output "website_url" {
  description = "Public HTTPS endpoint serving the demo HTML."
  value       = "https://${azurerm_linux_web_app.main.default_hostname}"
}

output "web_app_name" {
  description = "Azure resource name of the web app."
  value       = azurerm_linux_web_app.main.name
}

output "resource_group_name" {
  description = "Resource group containing the web app + plan."
  value       = azurerm_resource_group.main.name
}

output "service_plan_id" {
  description = "ID of the underlying App Service Plan."
  value       = azurerm_service_plan.main.id
}

output "default_hostname" {
  description = "App Service default hostname (without scheme)."
  value       = azurerm_linux_web_app.main.default_hostname
}

# ── Conditional outputs (only present when toggles are on) ────────────────

output "staging_slot_url" {
  description = "Staging slot HTTPS endpoint (empty when enable_staging_slot=false)."
  value       = var.enable_staging_slot ? "https://${azurerm_linux_web_app_slot.staging[0].default_hostname}" : ""
}

output "application_insights_connection_string" {
  description = "App Insights connection string (empty when enable_monitoring=false)."
  value       = var.enable_monitoring ? azurerm_application_insights.main[0].connection_string : ""
  sensitive   = true
}

output "log_analytics_workspace_id" {
  description = "Log Analytics Workspace ID for queries (empty when enable_monitoring=false)."
  value       = var.enable_monitoring ? azurerm_log_analytics_workspace.main[0].id : ""
}

output "backup_storage_account" {
  description = "Storage account name used for App Service backups (empty when enable_backup=false)."
  value       = var.enable_backup ? azurerm_storage_account.backup[0].name : ""
}
