variable "project_name" {
  description = "Tag prefix and resource name root."
  type        = string
}

variable "environment" {
  description = "Environment label (dev / staging / prod)."
  type        = string
}

variable "lambda_memory" {
  description = "Lambda memory allocation in MB."
  type        = number
  default     = 128
  validation {
    condition     = var.lambda_memory >= 128 && var.lambda_memory <= 3008
    error_message = "lambda_memory must be between 128 and 3008 MB."
  }
}

variable "lambda_timeout" {
  description = "Lambda timeout in seconds."
  type        = number
  default     = 30
  validation {
    condition     = var.lambda_timeout >= 1 && var.lambda_timeout <= 900
    error_message = "lambda_timeout must be between 1 and 900 seconds."
  }
}

variable "tags" {
  description = "Additional tags merged onto every module-managed resource."
  type        = map(string)
  default     = {}
}
