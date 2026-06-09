variable "project_name" {
  description = "Tag prefix for all VPC resources."
  type        = string
  default     = "archie-test"
}

variable "environment" {
  description = "Environment label (dev, staging, prod)."
  type        = string
  default     = "dev"
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC."
  type        = string
  default     = "10.0.0.0/16"
}

variable "subnet_count" {
  description = "Number of public subnets to carve."
  type        = number
  default     = 2
}

variable "tags" {
  description = "Custom tags applied to every resource."
  type        = map(string)
  default     = { ManagedBy = "Archie" }
}
