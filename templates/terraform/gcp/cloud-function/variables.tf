variable "project_name" {
  description = "Resource name root. Used to derive RFC1035-safe GCP names."
  type        = string
  default     = "archie-test"
}

variable "environment" {
  description = "Environment label (dev, staging, prod). Used in labels."
  type        = string
  default     = "dev"
}

variable "region" {
  description = "GCP region for the function and source bucket."
  type        = string
  default     = "us-central1"
}

variable "runtime" {
  description = "Cloud Function runtime (e.g. python311, python312, nodejs20)."
  type        = string
  default     = "python311"
}

variable "entry_point" {
  description = "Name of the function inside main.py that handles requests."
  type        = string
  default     = "hello"
}

variable "memory_mb" {
  description = "Memory allocation in MB."
  type        = number
  default     = 256
  validation {
    condition     = var.memory_mb >= 128 && var.memory_mb <= 32768
    error_message = "memory_mb must be between 128 and 32768."
  }
}

variable "timeout_seconds" {
  description = "Function execution timeout in seconds."
  type        = number
  default     = 60
  validation {
    condition     = var.timeout_seconds >= 1 && var.timeout_seconds <= 3600
    error_message = "timeout_seconds must be between 1 and 3600."
  }
}

variable "min_instances" {
  description = "Minimum number of warm instances. 0 = scale to zero."
  type        = number
  default     = 0
  validation {
    condition     = var.min_instances >= 0 && var.min_instances <= 1000
    error_message = "min_instances must be between 0 and 1000."
  }
}

variable "max_instances" {
  description = "Maximum number of concurrent instances."
  type        = number
  default     = 3
  validation {
    condition     = var.max_instances >= 1 && var.max_instances <= 1000
    error_message = "max_instances must be between 1 and 1000."
  }
}

variable "env_vars" {
  description = "Environment variables passed to the function at runtime."
  type        = map(string)
  default     = {}
}
