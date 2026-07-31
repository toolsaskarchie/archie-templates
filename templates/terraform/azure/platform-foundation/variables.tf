# -----------------------------------------------------------------------------
# Input variables (Azure)
# -----------------------------------------------------------------------------
# ESSENTIAL inputs (project_name, environment) have NO default. GOVERNED knobs
# carry safe defaults and are locked per policy. Public ingress is rejected.
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

variable "azure_subscription_id" {
  description = "Target Azure subscription id for the provider."
  type        = string
  default     = ""
}

variable "location" {
  description = "Azure region for all resources."
  type        = string
  default     = "eastus"
}

variable "address_space" {
  description = "CIDR block for the platform virtual network."
  type        = string
  default     = "10.20.0.0/16"

  validation {
    condition     = can(cidrhost(var.address_space, 0))
    error_message = "address_space must be a valid IPv4 CIDR block."
  }
}

variable "subnet_prefix" {
  description = "CIDR block for the application subnet."
  type        = string
  default     = "10.20.1.0/24"
}

variable "allowed_ingress_cidr" {
  description = "CIDR permitted to reach the application NSG. Corporate ranges only."
  type        = string
  default     = "10.0.0.0/8"

  validation {
    condition     = var.allowed_ingress_cidr != "0.0.0.0/0" && var.allowed_ingress_cidr != "*"
    error_message = "Public ingress (0.0.0.0/0) is not permitted — use a corporate CIDR range."
  }
}

variable "storage_min_tls" {
  description = "Minimum TLS version enforced on the storage account."
  type        = string
  default     = "TLS1_2"

  validation {
    condition     = contains(["TLS1_2"], var.storage_min_tls)
    error_message = "storage_min_tls must be TLS1_2."
  }
}

variable "blob_versioning_enabled" {
  description = "Enable blob versioning on the assets storage account."
  type        = bool
  default     = true
}

variable "blob_retention_days" {
  description = "Days to retain soft-deleted blobs."
  type        = number
  default     = 30

  validation {
    condition     = var.blob_retention_days >= 1 && var.blob_retention_days <= 365
    error_message = "blob_retention_days must be between 1 and 365."
  }
}

variable "log_retention_days" {
  description = "Log Analytics workspace retention (days)."
  type        = number
  default     = 30

  validation {
    condition     = var.log_retention_days >= 30 && var.log_retention_days <= 730
    error_message = "log_retention_days must be between 30 and 730."
  }
}

variable "tags" {
  description = "Additional tags merged into the enterprise defaults."
  type        = map(string)
  default = {
    CostCenter = "platform-engineering"
  }
}
