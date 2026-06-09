variable "project_name" {
  description = "Tag prefix for EC2 instances."
  type        = string
}

variable "instance_type" {
  description = "EC2 instance size."
  type        = string
  default     = "t3.micro"
}

variable "instance_count" {
  description = "Number of backend EC2 instances to launch. Spread across subnet_ids round-robin."
  type        = number
  default     = 2
}

variable "subnet_ids" {
  description = "Subnet IDs to spread backend instances across."
  type        = list(string)
}

variable "backend_security_group_id" {
  description = "Backend security group ID (created by the alb module, accepts target_port from ALB SG only)."
  type        = string
}

variable "target_group_arn" {
  description = "Target group to register the instances with."
  type        = string
}

variable "target_port" {
  description = "Port the backend listens on (used for the target group attachment)."
  type        = number
  default     = 80
}

variable "tags" {
  description = "Common tags to apply to all resources."
  type        = map(string)
  default     = {}
}
