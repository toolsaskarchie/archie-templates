variable "project" {
  description = "Application/product identifier."
  type        = string
}
variable "environment" {
  description = "Environment tier (dev|staging|prod)."
  type        = string
}
variable "vpc_id" {
  description = "Existing VPC to place the database in."
  type        = string
}
variable "subnet_ids" {
  description = "Private subnets for the DB subnet group."
  type        = list(string)
}
variable "instance_class" {
  description = "RDS instance class."
  type        = string
}
variable "allocated_storage" {
  description = "Storage in GiB."
  type        = number
  default     = 100
}
variable "multi_az" {
  description = "Run a standby in a second AZ."
  type        = bool
}
variable "backup_retention_days" {
  description = "Automated backup retention."
  type        = number
}
variable "deletion_protection" {
  description = "Block accidental deletion."
  type        = bool
}
variable "kms_key_arn" {
  description = "CMK for storage + performance insights."
  type        = string
}
variable "allowed_security_group_ids" {
  description = "SGs permitted to reach 5432."
  type        = list(string)
}
variable "tags" {
  description = "Mandatory org tags."
  type        = map(string)
}

# The master user's NAME only. Its password is generated and rotated by AWS
# (manage_master_user_password in main.tf), so there is no secret to declare
# here, hand to Archie, or leave in state.
variable "master_username" {
  description = "Master username for the Postgres instance."
  type        = string
  default     = "archie_admin"
}
