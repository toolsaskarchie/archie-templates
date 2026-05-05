variable "project_name" {
  description = "Tag prefix for AppGW resources."
  type        = string
}

variable "resource_group_name" {
  description = "Resource group where the AppGW is created."
  type        = string
}

variable "location" {
  description = "Azure region."
  type        = string
}

variable "subnet_id" {
  description = "Subnet to deploy the AppGW into. Must be a /27 or larger dedicated to AppGW."
  type        = string
}

variable "backend_ip_address" {
  description = "Private IP of the backend VM the AppGW forwards traffic to."
  type        = string
}

variable "tags" {
  description = "Common tags to apply to all resources."
  type        = map(string)
  default     = {}
}
