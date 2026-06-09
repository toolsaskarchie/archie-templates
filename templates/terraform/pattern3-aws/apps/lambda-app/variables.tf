variable "project_name" {
  description = "Tag prefix for Lambda + supporting resources."
  type        = string
  default     = "archie-test"
}

variable "environment" {
  description = "Environment label (dev, staging, prod)."
  type        = string
  default     = "dev"
}

variable "lambda_memory" {
  description = "Lambda memory in MB."
  type        = number
  default     = 128
}

variable "lambda_timeout" {
  description = "Lambda timeout in seconds."
  type        = number
  default     = 30
}

variable "tags" {
  description = "Custom tags applied to every resource."
  type        = map(string)
  default     = { ManagedBy = "Archie" }
}
