variable "project" {
  description = "Application/product identifier."
  type        = string
}
variable "environment" {
  description = "Environment tier (dev|staging|prod)."
  type        = string
}
variable "region" {
  description = "AWS region for this stack."
  type        = string
}
variable "vpc_cidr" {
  description = "CIDR block for the VPC."
  type        = string
}
variable "az_count" {
  description = "How many AZs to span."
  type        = number
  default     = 2
}
variable "enable_nat_gateway" {
  description = "Route private subnets via NAT."
  type        = bool
  default     = true
}
variable "flow_log_retention_days" {
  description = "VPC flow log retention."
  type        = number
  default     = 30
}
variable "kms_key_arn" {
  description = "CMK used to encrypt flow logs."
  type        = string
}
variable "tags" {
  description = "Mandatory org tags."
  type        = map(string)
}
