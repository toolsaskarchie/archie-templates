variable "project_name" {
  description = "Tag prefix and resource name root."
  type        = string
  default     = "myapp"
}

variable "environment" {
  description = "Environment label."
  type        = string
  default     = "dev"
}

variable "location" {
  description = "Azure region."
  type        = string
  default     = "eastus"
}

variable "runtime_version" {
  description = "Python runtime version for the Function App."
  type        = string
  default     = "3.11"
  validation {
    condition     = contains(["3.9", "3.10", "3.11", "3.12"], var.runtime_version)
    error_message = "runtime_version must be 3.9, 3.10, 3.11, or 3.12."
  }
}

variable "enable_app_insights" {
  description = "Provision Application Insights for the function app."
  type        = bool
  default     = false
}

variable "enable_slot" {
  description = "Provision a staging deployment slot (Prod-only feature)."
  type        = bool
  default     = false
}

variable "always_on" {
  description = "Keep the function warm (NOT supported on Consumption plan)."
  type        = bool
  default     = false
}

variable "page_title" {
  description = "Page title shown in the HTML landing page."
  type        = string
  default     = "AskArchie — Cloud Standards Platform"
}

variable "button_color" {
  description = "Hex color for the refresh button."
  type        = string
  default     = "#3B82F6"
}

variable "tags" {
  description = "Additional tags merged into every resource."
  type        = map(string)
  default     = {}
}
