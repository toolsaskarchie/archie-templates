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
  description = "Azure region. westus default — better residual quota on new subs than eastus. PE can lock per profile."
  type        = string
  default     = "westus"
}

variable "resource_group_name" {
  description = "Resource group. Created if missing."
  type        = string
  default     = ""
}

variable "sku_name" {
  description = "App Service Plan SKU. F1 = free (shared hosting, no VM quota, no always_on, no staging slots) — default for nonprod. B1 = smallest dedicated. S1+ supports autoscale + staging slots — typical prod. PE locks per profile (nonprod=F1, prod=S1+)."
  type        = string
  default     = "F1"
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
  description = "Keep the app warm. F1 SKU does NOT support always_on — must be false on F1. PE locks false on nonprod (F1), true on prod (S1+)."
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
  description = "Log Analytics workspace retention (Azure: 30–730 days). Only used when enable_monitoring is true. Typical profile values: nonprod=30, prod=90. PE locks per profile in the governance editor."
  type        = number
  default     = 30
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
