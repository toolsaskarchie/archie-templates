variable "project_name" {
  description = "Tag prefix for all resources."
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
  default     = "10.30.0.0/16"
}

variable "instance_type" {
  description = "EC2 instance type."
  type        = string
  default     = "t3.micro"
}

variable "ec2_instance_count" {
  description = "Number of EC2 instances behind the ALB."
  type        = number
  default     = 2
}

variable "allowed_cidrs" {
  description = "CIDRs permitted to reach the ALB."
  type        = list(string)
  default     = ["0.0.0.0/0"]
}
