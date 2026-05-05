variable "project_name" {
  description = "Tag prefix for ALB resources."
  type        = string
}

variable "vpc_id" {
  description = "VPC where the ALB and target group are created."
  type        = string
}

variable "subnet_ids" {
  description = "Subnet IDs for the ALB (must span at least 2 AZs)."
  type        = list(string)
}

variable "allowed_cidrs" {
  description = "CIDR blocks allowed to reach the ALB on port 80."
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "tags" {
  description = "Common tags to apply to all resources."
  type        = map(string)
  default     = {}
}
