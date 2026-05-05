output "appgw_id" {
  description = "ID of the Application Gateway."
  value       = azurerm_application_gateway.main.id
}

output "public_ip_address" {
  description = "Public IP address of the Application Gateway."
  value       = azurerm_public_ip.appgw.ip_address
}

output "public_fqdn" {
  description = "Public FQDN of the Application Gateway (Azure-assigned domain)."
  value       = azurerm_public_ip.appgw.fqdn
}
