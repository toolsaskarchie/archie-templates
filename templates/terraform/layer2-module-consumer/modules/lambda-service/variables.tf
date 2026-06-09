variable "project_name" {
  description = "Tag prefix and resource name root."
  type        = string
}

variable "environment" {
  description = "Environment label (dev / staging / prod)."
  type        = string
}

variable "function_name_suffix" {
  description = "Suffix appended after project + environment in the Lambda function name."
  type        = string
  default     = "function"
}

variable "runtime" {
  description = "Lambda runtime."
  type        = string
  default     = "python3.12"
}

variable "handler" {
  description = "Lambda handler entrypoint."
  type        = string
  default     = "lambda_function.lambda_handler"
}

variable "memory_size" {
  description = "Lambda memory allocation in MB."
  type        = number
  default     = 256
  validation {
    condition     = var.memory_size >= 128 && var.memory_size <= 10240
    error_message = "memory_size must be between 128 and 10240 MB."
  }
}

variable "timeout" {
  description = "Lambda timeout in seconds."
  type        = number
  default     = 15
  validation {
    condition     = var.timeout >= 1 && var.timeout <= 900
    error_message = "timeout must be between 1 and 900 seconds."
  }
}

variable "reserved_concurrency" {
  description = "Reserved concurrency limit, 0 = no reservation."
  type        = number
  default     = 0
  validation {
    condition     = var.reserved_concurrency >= 0
    error_message = "reserved_concurrency must be 0 or greater."
  }
}

variable "environment_variables" {
  description = "Map merged into the Lambda's runtime environment."
  type        = map(string)
  default     = {}
}

variable "enable_dlq" {
  description = "Create SQS dead letter queue for failed invocations."
  type        = bool
  default     = false
}

variable "enable_xray" {
  description = "Enable X-Ray active tracing."
  type        = bool
  default     = false
}

variable "log_retention_days" {
  description = "CloudWatch log retention period in days."
  type        = number
  default     = 7
  validation {
    condition = contains([
      1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1096, 1827, 2192, 2557, 2922, 3288, 3653
    ], var.log_retention_days)
    error_message = "log_retention_days must be a valid CloudWatch retention period."
  }
}

variable "kms_key_arn" {
  description = "KMS key ARN for env var + log group encryption. Empty = AWS-managed key."
  type        = string
  default     = ""
}

variable "enable_alarms" {
  description = "Create a CloudWatch errors-metric alarm."
  type        = bool
  default     = false
}

variable "alarm_threshold" {
  description = "Errors-per-period threshold that fires the alarm."
  type        = number
  default     = 1
}

variable "alarm_sns_topic_arn" {
  description = "SNS topic ARN to notify on alarm. Empty = no alarm action."
  type        = string
  default     = ""
}

variable "tags" {
  description = "Tags applied to every resource."
  type        = map(string)
  default     = {}
}

variable "additional_tags" {
  description = "Extra tags merged on top of `tags`."
  type        = map(string)
  default     = {}
}

variable "role_name_override" {
  description = "Override the generated IAM role name. Empty = auto-generated."
  type        = string
  default     = ""
}
