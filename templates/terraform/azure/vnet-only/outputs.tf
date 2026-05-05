output "resource_group_name" {
  description = "Name of the resource group."
  value       = azurerm_resource_group.main.name
}

output "vnet_id" {
  description = "ID of the Virtual Network."
  value       = azurerm_virtual_network.main.id
}

output "vnet_name" {
  description = "Name of the Virtual Network."
  value       = azurerm_virtual_network.main.name
}

output "subnet_ids" {
  description = "List of subnet IDs."
  value       = azurerm_subnet.main[*].id
}

output "address_space" {
  description = "Address space of the VNet."
  value       = azurerm_virtual_network.main.address_space
}
