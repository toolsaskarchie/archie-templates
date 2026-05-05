output "vm_id" {
  description = "ID of the Linux VM."
  value       = azurerm_linux_virtual_machine.main.id
}

output "private_ip" {
  description = "Private IP of the VM (used by AppGW backend pool)."
  value       = azurerm_network_interface.main.private_ip_address
}

output "nic_id" {
  description = "ID of the network interface."
  value       = azurerm_network_interface.main.id
}
