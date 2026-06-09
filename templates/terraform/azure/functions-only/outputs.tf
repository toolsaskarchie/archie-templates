output "resource_group_name" {
  description = "Name of the resource group."
  value       = azurerm_resource_group.main.name
}

output "function_app_id" {
  description = "Full Azure resource ID of the function app."
  value       = azurerm_linux_function_app.main.id
}

output "function_app_name" {
  description = "Function app name."
  value       = azurerm_linux_function_app.main.name
}

output "function_app_default_hostname" {
  description = "Default hostname for the function app (e.g. <name>.azurewebsites.net)."
  value       = azurerm_linux_function_app.main.default_hostname
}

output "storage_account_name" {
  description = "Backing storage account name."
  value       = azurerm_storage_account.main.name
}

output "app_insights_instrumentation_key" {
  description = "Application Insights instrumentation key wired into the function app."
  value       = azurerm_application_insights.main.instrumentation_key
  sensitive   = true
}
