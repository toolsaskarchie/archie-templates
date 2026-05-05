output "resource_group_name" {
  description = "Name of the resource group."
  value       = azurerm_resource_group.main.name
}

output "vnet_id" {
  description = "ID of the Virtual Network."
  value       = module.vnet.vnet_id
}

output "appgw_id" {
  description = "ID of the Application Gateway."
  value       = module.appgw.appgw_id
}

output "appgw_public_ip" {
  description = "Public IP address of the Application Gateway."
  value       = module.appgw.public_ip_address
}

output "appgw_public_fqdn" {
  description = "Public FQDN of the Application Gateway."
  value       = module.appgw.public_fqdn
}

output "vm_id" {
  description = "ID of the backend VM."
  value       = module.vm.vm_id
}

output "vm_private_ip" {
  description = "Private IP of the backend VM."
  value       = module.vm.private_ip
}
