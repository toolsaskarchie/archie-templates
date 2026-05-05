variable "project_name" {
  description = "Tag prefix and resource name root."
  type        = string
  default     = "archie-test"
}

variable "environment" {
  description = "Environment label (dev, staging, prod). Used in tags."
  type        = string
  default     = "dev"
}

variable "location" {
  description = "Azure region."
  type        = string
  default     = "eastus"
}

variable "resource_group_name" {
  description = "Name of the resource group to create. Resources land here."
  type        = string
  default     = "archie-test-rg"
}

variable "vnet_cidr" {
  description = "CIDR block for the VNet. Subnets are carved as /24 within."
  type        = string
  default     = "10.0.0.0/16"
}

variable "vm_size" {
  description = "Size of the backend VM."
  type        = string
  default     = "Standard_B1s"
}

variable "admin_username" {
  description = "Admin username for the backend VM."
  type        = string
  default     = "azureuser"
}

variable "admin_password" {
  description = "Admin password for the backend VM. For demo only — use SSH keys in production."
  type        = string
  sensitive   = true
  default     = "ArchieDemo!2026"
}

variable "allowed_cidrs" {
  description = "CIDR blocks allowed to reach the Application Gateway on port 80."
  type        = list(string)
  default     = ["0.0.0.0/0"]
}
