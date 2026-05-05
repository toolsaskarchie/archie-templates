variable "project_name" {
  description = "Tag prefix for all VPC resources."
  type        = string
  default     = "archie-test"
}

variable "environment" {
  description = "Environment label (dev, staging, prod). Used in tags."
  type        = string
  default     = "dev"
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC. Subnets are carved as /24 within."
  type        = string
  default     = "10.0.0.0/16"
}

variable "subnet_count" {
  description = "Number of public subnets to create across availability zones."
  type        = number
  default     = 2
  validation {
    condition     = var.subnet_count >= 1 && var.subnet_count <= 4
    error_message = "subnet_count must be between 1 and 4."
  }
}

variable "tags" {
  description = "Custom tags applied to every resource. Common pattern is to lock organization-required tags (Team, CostCenter, ManagedBy) at the blueprint level so they can't be removed by hand from the cloud. Drift detection flags any tag change; remediation restores the locked set."
  type        = map(string)
  default = {
    ManagedBy = "archie"
  }
}
