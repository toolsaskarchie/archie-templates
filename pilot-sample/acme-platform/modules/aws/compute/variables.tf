variable "project" {
  description = "Application/product identifier."
  type        = string
}
variable "environment" {
  description = "Environment tier (dev|staging|prod)."
  type        = string
}
variable "vpc_id" {
  description = "Existing VPC to run the service in."
  type        = string
}
variable "private_subnet_ids" {
  description = "Private subnets for tasks."
  type        = list(string)
}
variable "public_subnet_ids" {
  description = "Public subnets for the ALB."
  type        = list(string)
}
variable "instance_type" {
  description = "EC2 type for the capacity provider."
  type        = string
}
variable "desired_count" {
  description = "Number of service tasks."
  type        = number
}
variable "ingress_cidrs" {
  description = "CIDRs allowed to reach the ALB."
  type        = list(string)
}
variable "certificate_arn" {
  description = "ACM cert for the HTTPS listener."
  type        = string
}
variable "kms_key_arn" {
  description = "CMK for log encryption."
  type        = string
}
variable "log_retention_days" {
  description = "CloudWatch retention."
  type        = number
  default     = 30
}
variable "tags" {
  description = "Mandatory org tags."
  type        = map(string)
}
