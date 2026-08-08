output "resource_group_name" {
  description = "Resource group."
  value       = azurerm_resource_group.main.name
}
output "vnet_id" {
  description = "VNet id."
  value       = azurerm_virtual_network.main.id
}
output "private_subnet_id" {
  description = "Private subnet id."
  value       = azurerm_subnet.private.id
}
