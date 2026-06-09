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
  description = "EC2 instance size for backend web servers."
  type        = string
  default     = "t3.micro"
}

variable "ec2_instance_count" {
  description = "Number of backend EC2 instances. Spread across AZs round-robin."
  type        = number
  default     = 2
}

variable "target_port" {
  description = "Port the backend listens on (also the ALB target group port)."
  type        = number
  default     = 80
}

variable "internal" {
  description = "If true, the ALB is internal (no public DNS, VPC-only)."
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

variable "allowed_cidrs" {
  description = "CIDR blocks allowed to reach the ALB on the listener port(s)."
  type        = list(string)
  default     = ["0.0.0.0/0"]
}
