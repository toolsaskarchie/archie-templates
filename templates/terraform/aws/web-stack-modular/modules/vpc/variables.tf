variable "project_name" {
  description = "Tag prefix for VPC resources."
  type        = string
}

variable "environment" {
  description = "Environment label."
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC."
  type        = string
  default     = "10.0.0.0/16"
}

variable "tags" {
  description = "Common tags to apply to all resources."
  type        = map(string)
  default     = {}
}
