output "vnet_id" {
  description = "ID of the Virtual Network."
  value       = azurerm_virtual_network.main.id
}

output "vnet_name" {
  description = "Name of the Virtual Network."
  value       = azurerm_virtual_network.main.name
}

output "appgw_subnet_id" {
  description = "ID of the subnet hosting the Application Gateway."
  value       = azurerm_subnet.appgw.id
}

output "backend_subnet_id" {
  description = "ID of the subnet hosting the backend VMs."
  value       = azurerm_subnet.backend.id
}
