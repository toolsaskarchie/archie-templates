variable "project_name" {
  description = "Resource name root + tag prefix."
  type        = string
  default     = "myapp"
}

variable "environment" {
  description = "Environment label (dev / staging / prod)."
  type        = string
  default     = "dev"
}

variable "location" {
  description = "Azure region."
  type        = string
  default     = "eastus"
}

variable "resource_group_name" {
  description = "Resource group. Created if missing."
  type        = string
  default     = ""
}

variable "sku_name" {
  description = "App Service Plan SKU. B1 is the smallest always-on tier; F1 is free but limited to 60 CPU min/day and cold-starts hard."
  type        = string
  default     = "B1"
  validation {
    condition     = contains(["F1", "B1", "B2", "B3", "S1", "S2", "S3", "P0v3", "P1v3", "P2v3"], var.sku_name)
    error_message = "Use a supported Linux App Service SKU (F1, B1-B3, S1-S3, P0v3-P2v3)."
  }
}

variable "python_version" {
  description = "Python runtime for the Linux web app."
  type        = string
  default     = "3.12"
}

variable "page_title" {
  description = "Page title and subtitle text — mirrors the AWS Lambda demo so cross-cloud diffs are visible."
  type        = string
  default     = "AskArchie — Cloud Standards Platform"
}

variable "button_color" {
  description = "Hex color for the refresh button."
  type        = string
  default     = "#3B82F6"
}

variable "https_only" {
  description = "Force HTTPS-only on the web app. Strongly recommended for prod."
  type        = bool
  default     = true
}

variable "always_on" {
  description = "Keep the app warm. F1 SKU does NOT support always_on — set false on F1."
  type        = bool
  default     = true
}

variable "tags" {
  description = "Extra tags merged into all resources."
  type        = map(string)
  default     = {}
}
