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
  description = "App Service Plan SKU. B1 is the smallest always-on tier; S1+ supports autoscale + staging slots; F1 is free but limited."
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
  description = "Keep the app warm. F1 SKU does NOT support always_on — set false on F1. Default false to fit dev / B1; PE locks true on the prod profile."
  type        = bool
  default     = false
}

# ── Conditional resources (governance toggles) ────────────────────────────
# These mirror the AWS Lambda demo's enable_dlq / enable_xray pattern:
# bool toggles that gate `count = var.x ? 1 : 0` resources, so a single
# blueprint produces a thin dev stack and a fat prod stack. The PE locks
# them per-profile in the governance editor.

variable "enable_monitoring" {
  description = "Create Application Insights + Log Analytics Workspace and wire connection string into the web app. Lock true on prod, false on dev."
  type        = bool
  default     = false
}

variable "log_retention_days" {
  description = "Log Analytics workspace retention. Only used when enable_monitoring is true."
  type        = number
  default     = 30
  validation {
    condition     = var.log_retention_days >= 30 && var.log_retention_days <= 730
    error_message = "Log Analytics retention must be between 30 and 730 days."
  }
}

variable "enable_staging_slot" {
  description = "Create a deployment slot for blue/green swap. Requires S1+ SKU (Basic tier does NOT support slots). Lock true on prod, false on dev."
  type        = bool
  default     = false
}

variable "enable_backup" {
  description = "Create a Storage Account + container for App Service backup snapshots. Backup schedule configured nightly. Lock true on prod, false on dev."
  type        = bool
  default     = false
}

variable "tags" {
  description = "Extra tags merged into all resources."
  type        = map(string)
  default     = {}
}
