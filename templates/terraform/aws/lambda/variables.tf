variable "project_name" {
  description = "Tag prefix and resource name root."
  type        = string
  default     = "archie-demo"
}

variable "environment" {
  description = "Environment label for resource tagging."
  type        = string
  default     = "dev"
  validation {
    condition     = contains(["dev", "staging", "production"], var.environment)
    error_message = "Environment must be dev, staging, or production."
  }
}

variable "lambda_memory" {
  description = "Lambda memory allocation in MB (128-10240)."
  type        = number
  default     = 256
  validation {
    condition     = var.lambda_memory >= 128 && var.lambda_memory <= 10240
    error_message = "Lambda memory must be between 128 and 10240 MB."
  }
}

variable "lambda_timeout" {
  description = "Lambda timeout in seconds (1-900)."
  type        = number
  default     = 30
  validation {
    condition     = var.lambda_timeout >= 1 && var.lambda_timeout <= 900
    error_message = "Lambda timeout must be between 1 and 900 seconds."
  }
}

variable "auth_type" {
  description = "Function URL authentication type (NONE for public access)."
  type        = string
  default     = "NONE"
  validation {
    condition     = contains(["NONE", "AWS_IAM"], var.auth_type)
    error_message = "Auth type must be NONE or AWS_IAM."
  }
}

variable "button_color" {
  description = "Hex color code for the refresh button."
  type        = string
  default     = "#3B82F6"
}

variable "page_title" {
  description = "Page title and subtitle text displayed on the page."
  type        = string
  default     = "AskArchie — Cloud Standards Platform"
}

variable "log_retention_days" {
  description = "CloudWatch log retention period in days."
  type        = number
  default     = 7
}

variable "table_name" {
  description = "Name of the DynamoDB table."
  type        = string
  default     = "archie-demo-table"
}

variable "partition_key" {
  description = "Partition key attribute name for the DynamoDB table."
  type        = string
  default     = "id"
}

variable "read_capacity" {
  description = "Read capacity units for the DynamoDB table."
  type        = number
  default     = 5
  validation {
    condition     = var.read_capacity >= 1
    error_message = "Read capacity must be at least 1."
  }
}

variable "write_capacity" {
  description = "Write capacity units for the DynamoDB table."
  type        = number
  default     = 5
  validation {
    condition     = var.write_capacity >= 1
    error_message = "Write capacity must be at least 1."
  }
}

variable "tags" {
  description = "Additional tags to apply to all resources."
  type        = map(string)
  default     = {}
}
