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
  description = "Name of the resource group to create. The VNet lands here."
  type        = string
  default     = "archie-test-rg"
}

variable "vnet_cidr" {
  description = "CIDR block for the VNet. Subnets are carved as /24 within."
  type        = string
  default     = "10.0.0.0/16"
}

variable "subnet_count" {
  description = "Number of subnets to create."
  type        = number
  default     = 2
  validation {
    condition     = var.subnet_count >= 1 && var.subnet_count <= 4
    error_message = "subnet_count must be between 1 and 4."
  }
}
