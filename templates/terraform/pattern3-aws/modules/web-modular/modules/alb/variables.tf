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
  description = "CIDR blocks allowed to reach the ALB on the listener port(s)."
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "target_port" {
  description = "Port the backend listens on (also the target group port)."
  type        = number
  default     = 80
}

variable "internal" {
  description = "If true, the ALB has no public DNS - reachable only from inside the VPC."
  type        = bool
  default     = false
}

variable "enable_https" {
  description = "Add an HTTPS listener on port 443 (requires certificate_arn)."
  type        = bool
  default     = false
}

variable "certificate_arn" {
  description = "ACM certificate ARN for the HTTPS listener. Required when enable_https=true."
  type        = string
  default     = ""
}

variable "tags" {
  description = "Common tags to apply to all resources."
  type        = map(string)
  default     = {}
}
