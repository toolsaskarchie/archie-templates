variable "project_name" {
  description = "Tag prefix for VM resources."
  type        = string
}

variable "resource_group_name" {
  description = "Resource group where the VM is created."
  type        = string
}

variable "location" {
  description = "Azure region."
  type        = string
}

variable "subnet_id" {
  description = "Subnet to launch the VM in."
  type        = string
}

variable "vm_size" {
  description = "Azure VM size."
  type        = string
  default     = "Standard_B1s"
}

variable "admin_username" {
  description = "Admin username for the VM."
  type        = string
  default     = "azureuser"
}

variable "admin_password" {
  description = "Admin password. Use SSH keys in production."
  type        = string
  sensitive   = true
}

variable "tags" {
  description = "Common tags to apply to all resources."
  type        = map(string)
  default     = {}
}
