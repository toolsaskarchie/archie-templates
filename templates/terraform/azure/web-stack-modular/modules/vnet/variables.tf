variable "project_name" {
  description = "Tag prefix for VNet resources."
  type        = string
}

variable "resource_group_name" {
  description = "Resource group where the VNet is created."
  type        = string
}

variable "location" {
  description = "Azure region."
  type        = string
}

variable "vnet_cidr" {
  description = "CIDR block for the VNet."
  type        = string
  default     = "10.0.0.0/16"
}

variable "allowed_cidrs" {
  description = "CIDR blocks allowed to reach the AppGW subnet on port 80."
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "tags" {
  description = "Common tags to apply to all resources."
  type        = map(string)
  default     = {}
}
