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

variable "gcp_project" {
  description = "GCP project ID to deploy into."
  type        = string
}

variable "region" {
  description = "GCP region."
  type        = string
  default     = "us-central1"
}

variable "runtime" {
  description = "Cloud Functions Python runtime."
  type        = string
  default     = "python311"
  validation {
    condition     = contains(["python39", "python310", "python311", "python312"], var.runtime)
    error_message = "runtime must be python39, python310, python311, or python312."
  }
}

variable "memory" {
  description = "Function memory allocation (e.g. 256M, 512M, 1G)."
  type        = string
  default     = "256M"
}

variable "timeout_seconds" {
  description = "Function timeout in seconds."
  type        = number
  default     = 30
  validation {
    condition     = var.timeout_seconds >= 1 && var.timeout_seconds <= 540
    error_message = "timeout_seconds must be between 1 and 540."
  }
}

variable "enable_vpc_connector" {
  description = "Provision a Serverless VPC connector (Prod-only feature)."
  type        = bool
  default     = false
}

variable "page_title" {
  description = "Page title shown in the HTML landing page."
  type        = string
  default     = "AskArchie — Cloud Standards Platform"
}

variable "button_color" {
  description = "Hex color for the refresh button."
  type        = string
  default     = "#3B82F6"
}

variable "labels" {
  description = "Additional labels merged into every resource."
  type        = map(string)
  default     = {}
}
