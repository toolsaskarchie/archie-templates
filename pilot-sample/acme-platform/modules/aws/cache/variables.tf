variable "project" {
  description = "Application/product identifier."
  type        = string
}
variable "environment" {
  description = "Environment tier (dev|staging|prod)."
  type        = string
}
variable "vpc_id" {
  description = "Existing VPC to place the cache in."
  type        = string
}
variable "subnet_ids" {
  description = "Private subnets for the cache subnet group."
  type        = list(string)
}
variable "node_type" {
  description = "ElastiCache node type."
  type        = string
}
variable "replica_count" {
  description = "Replicas per shard."
  type        = number
}
variable "multi_az_enabled" {
  description = "Enable multi-AZ with auto failover."
  type        = bool
}
variable "snapshot_retention_limit" {
  description = "Days of automatic snapshots."
  type        = number
}
variable "kms_key_arn" {
  description = "CMK for at-rest encryption."
  type        = string
}
variable "allowed_security_group_ids" {
  description = "SGs permitted to reach 6379."
  type        = list(string)
}
variable "tags" {
  description = "Mandatory org tags."
  type        = map(string)
}
