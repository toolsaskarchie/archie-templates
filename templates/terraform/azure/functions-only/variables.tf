variable "project_name" {
  description = "Tag prefix and resource name root. Also seeds the globally unique storage account name."
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
  description = "Name of the resource group to create. The function app and its storage land here."
  type        = string
  default     = "archie-test-rg"
}

variable "function_runtime" {
  description = "Function app runtime stack. Only python is supported by this template today."
  type        = string
  default     = "python"
  validation {
    condition     = var.function_runtime == "python"
    error_message = "function_runtime must be python (only supported runtime in this template)."
  }
}

variable "python_version" {
  description = "Python version for the function app site_config.application_stack."
  type        = string
  default     = "3.11"
}

variable "storage_tier" {
  description = "Storage account tier. Standard for cost, Premium for low-latency workloads."
  type        = string
  default     = "Standard"
  validation {
    condition     = contains(["Standard", "Premium"], var.storage_tier)
    error_message = "storage_tier must be Standard or Premium."
  }
}

variable "storage_replication" {
  description = "Storage replication: LRS (cheap, single zone), GRS (geo-redundant for prod)."
  type        = string
  default     = "LRS"
  validation {
    condition     = contains(["LRS", "GRS", "RAGRS", "ZRS"], var.storage_replication)
    error_message = "storage_replication must be one of LRS, GRS, RAGRS, ZRS."
  }
}

variable "app_settings" {
  description = "Additional app settings to merge into the function app. Map of string to string."
  type        = map(string)
  default     = {}
}
