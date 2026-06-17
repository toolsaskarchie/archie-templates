variable "project_name" {
  description = "Tag prefix and resource name root. Typically locked by the PE."
  type        = string
  default     = "archie-demo-lambda"
}

variable "environment" {
  description = "Environment label (nonprod, prod). Drives which governance profile applies."
  type        = string
  default     = "nonprod"
}

# ── Governable levers ────────────────────────────────────────────────────────
variable "lambda_memory" {
  description = "Lambda memory (MB). Profile lever — non-prod 256, prod locked higher."
  type        = number
  default     = 256
}

variable "lambda_timeout" {
  description = "Lambda timeout (seconds). Profile lever."
  type        = number
  default     = 15
}

variable "log_retention_days" {
  description = "CloudWatch log retention (days). Profile lever — non-prod 7, prod 90+."
  type        = number
  default     = 7
}

variable "reserved_concurrency" {
  description = "Reserved concurrent executions (0 = unreserved). Profile lever."
  type        = number
  default     = 0
}

variable "enable_xray" {
  description = "Enable X-Ray tracing. Profile lever — typically locked on in prod."
  type        = bool
  default     = false
}

variable "enable_dlq" {
  description = "Provision a dead-letter queue. Profile lever — typically locked on in prod."
  type        = bool
  default     = false
}

variable "tags" {
  description = "Additional tags merged into all resources."
  type        = map(string)
  default     = {}
}
