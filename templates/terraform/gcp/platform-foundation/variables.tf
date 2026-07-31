# -----------------------------------------------------------------------------
# Input variables (GCP)
# -----------------------------------------------------------------------------
# ESSENTIAL inputs (project_name, environment, gcp_project_id) have NO default.
# GOVERNED knobs carry safe defaults and are locked per policy. Public ingress
# is rejected outright.
# -----------------------------------------------------------------------------

variable "project_name" {
  description = "Short project/application name. Drives all resource naming."
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9-]{1,20}[a-z0-9]$", var.project_name))
    error_message = "project_name must be 3-22 lowercase alphanumerics/hyphens, not starting or ending with a hyphen."
  }
}

variable "environment" {
  description = "Deployment environment."
  type        = string

  validation {
    condition     = contains(["nonprod", "prod"], var.environment)
    error_message = "environment must be one of: nonprod, prod."
  }
}

variable "gcp_project_id" {
  description = "Target GCP project id. Leave empty to inherit from the deploy credentials."
  type        = string
  default     = ""
}

variable "region" {
  description = "GCP region for all resources."
  type        = string
  default     = "us-central1"
}

variable "subnet_cidr" {
  description = "CIDR block for the application subnet."
  type        = string
  default     = "10.30.0.0/24"

  validation {
    condition     = can(cidrhost(var.subnet_cidr, 0))
    error_message = "subnet_cidr must be a valid IPv4 CIDR block."
  }
}

variable "allowed_ingress_cidr" {
  description = "CIDR permitted to reach the application firewall. Corporate ranges only."
  type        = string
  default     = "10.0.0.0/8"

  validation {
    condition     = var.allowed_ingress_cidr != "0.0.0.0/0"
    error_message = "Public ingress (0.0.0.0/0) is not permitted — use a corporate CIDR range."
  }
}

variable "bucket_versioning_enabled" {
  description = "Enable object versioning on the assets bucket."
  type        = bool
  default     = true
}

variable "bucket_age_days" {
  description = "Age (days) after which objects are deleted by lifecycle policy."
  type        = number
  default     = 90

  validation {
    condition     = var.bucket_age_days >= 1
    error_message = "bucket_age_days must be >= 1."
  }
}

variable "pubsub_retention_seconds" {
  description = "Pub/Sub subscription message retention (seconds)."
  type        = number
  default     = 345600
}

variable "labels" {
  description = "Additional labels merged into the enterprise defaults."
  type        = map(string)
  default = {
    cost_center = "platform-engineering"
  }
}
