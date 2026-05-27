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
