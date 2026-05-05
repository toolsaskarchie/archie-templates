variable "project_name" {
  description = "Tag prefix and name for all resources."
  type        = string
  default     = "archie-test"
}

variable "environment" {
  description = "Environment label (dev, staging, prod). Used in tags."
  type        = string
  default     = "dev"
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC. Subnets are carved as /24 within this range."
  type        = string
  default     = "10.0.0.0/16"
}

variable "instance_type" {
  description = "EC2 instance size for the backend web server."
  type        = string
  default     = "t3.micro"
}

variable "enable_https" {
  description = "Reserved for future ACM/443 listener support."
  type        = bool
  default     = false
}

variable "allowed_cidrs" {
  description = "CIDR blocks allowed to reach the ALB on port 80."
  type        = list(string)
  default     = ["0.0.0.0/0"]
}
