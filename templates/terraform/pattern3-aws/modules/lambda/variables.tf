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

variable "lambda_memory" {
  description = "Lambda memory allocation in MB."
  type        = number
  default     = 256
  validation {
    condition     = var.lambda_memory >= 128 && var.lambda_memory <= 10240
    error_message = "Lambda memory must be between 128 and 10240 MB."
  }
}

variable "lambda_timeout" {
  description = "Lambda timeout in seconds."
  type        = number
  default     = 15
  validation {
    condition     = var.lambda_timeout >= 1 && var.lambda_timeout <= 900
    error_message = "Lambda timeout must be between 1 and 900 seconds."
  }
}

variable "log_retention_days" {
  description = "CloudWatch log retention period in days."
  type        = number
  default     = 7
  validation {
    condition = contains([
      1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1096, 1827, 2192, 2557, 2922, 3288, 3653
    ], var.log_retention_days)
    error_message = "Log retention days must be a valid CloudWatch retention period."
  }
}

variable "enable_dlq" {
  description = "Create SQS dead letter queue for failed invocations."
  type        = bool
  default     = false
}

variable "enable_xray" {
  description = "Enable X-Ray distributed tracing."
  type        = bool
  default     = false
}

variable "reserved_concurrency" {
  description = "Reserved concurrency limit, 0 = no reservation."
  type        = number
  default     = 0
  validation {
    condition     = var.reserved_concurrency >= 0
    error_message = "Reserved concurrency must be 0 or greater."
  }
}

variable "page_title" {
  description = "Page title and subtitle text."
  type        = string
  default     = "AskArchie - Cloud Standards Platform"
}

variable "button_color" {
  description = "Hex color for the refresh button."
  type        = string
  default     = "#3B82F6"
}

variable "tags" {
  description = "Additional tags to merge into all resources."
  type        = map(string)
  default     = {}
}
