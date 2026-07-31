# -----------------------------------------------------------------------------
# Input variables
# -----------------------------------------------------------------------------
# ESSENTIAL inputs (project_name, environment) have NO default — the deployer
# supplies them. GOVERNED knobs carry safe defaults and are locked per policy.
# Public ingress is rejected outright by an input validation.
# -----------------------------------------------------------------------------

variable "project_name" {
  description = "Short project/application name. Drives all resource naming."
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9-]{1,30}[a-z0-9]$", var.project_name))
    error_message = "project_name must be 3-32 lowercase alphanumerics/hyphens, not starting or ending with a hyphen."
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

variable "region" {
  description = "AWS region for all resources."
  type        = string
  default     = "us-east-1"
}

variable "vpc_cidr" {
  description = "CIDR block for the platform VPC."
  type        = string
  default     = "10.0.0.0/16"

  validation {
    condition     = can(cidrhost(var.vpc_cidr, 0))
    error_message = "vpc_cidr must be a valid IPv4 CIDR block."
  }
}

variable "allowed_ingress_cidr" {
  description = "CIDR permitted to reach the application security group. Corporate ranges only."
  type        = string
  default     = "10.0.0.0/8"

  validation {
    condition     = var.allowed_ingress_cidr != "0.0.0.0/0"
    error_message = "Public ingress (0.0.0.0/0) is not permitted — use a corporate CIDR range."
  }
}

variable "s3_versioning_enabled" {
  description = "Enable object versioning on the assets bucket."
  type        = bool
  default     = true
}

variable "s3_noncurrent_expiration_days" {
  description = "Days before noncurrent object versions expire."
  type        = number
  default     = 90

  validation {
    condition     = var.s3_noncurrent_expiration_days >= 1
    error_message = "s3_noncurrent_expiration_days must be >= 1."
  }
}

variable "dynamodb_point_in_time_recovery" {
  description = "Enable point-in-time recovery on the config table."
  type        = bool
  default     = true
}

variable "sqs_message_retention_seconds" {
  description = "How long SQS retains a message (seconds)."
  type        = number
  default     = 345600
}

variable "log_retention_days" {
  description = "CloudWatch log group retention (days)."
  type        = number
  default     = 30

  validation {
    condition     = contains([1, 3, 5, 7, 14, 30, 60, 90, 180, 365], var.log_retention_days)
    error_message = "log_retention_days must be a valid CloudWatch retention value."
  }
}

variable "tags" {
  description = "Additional tags merged into the enterprise defaults."
  type        = map(string)
  default = {
    CostCenter = "platform-engineering"
  }
}
