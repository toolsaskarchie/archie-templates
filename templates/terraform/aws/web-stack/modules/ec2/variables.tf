variable "project_name" {
  description = "Tag prefix for the EC2 instance."
  type        = string
}

variable "instance_type" {
  description = "EC2 instance size."
  type        = string
  default     = "t3.micro"
}

variable "subnet_id" {
  description = "Subnet to launch the instance in."
  type        = string
}

variable "security_group_id" {
  description = "Security group to attach to the instance (typically shared with the ALB)."
  type        = string
}

variable "target_group_arn" {
  description = "Target group to register the instance with."
  type        = string
}

variable "tags" {
  description = "Common tags to apply to all resources."
  type        = map(string)
  default     = {}
}
