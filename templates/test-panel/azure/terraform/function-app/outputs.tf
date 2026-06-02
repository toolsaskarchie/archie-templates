output "function_url" {
  description = "Public HTTPS URL of the Function App"
  value       = "https://${azurerm_linux_function_app.main.default_hostname}/api/http_landing"
}

output "function_app_name" {
  value = azurerm_linux_function_app.main.name
}

output "function_app_id" {
  value = azurerm_linux_function_app.main.id
}

output "resource_group_name" {
  value = azurerm_resource_group.main.name
}

output "storage_account_name" {
  value = azurerm_storage_account.main.name
}

output "app_insights_id" {
  description = "Application Insights resource ID (null when disabled)"
  value       = length(azurerm_application_insights.main) > 0 ? azurerm_application_insights.main[0].id : null
}
