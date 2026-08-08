variable "project" {
  description = "Application/product identifier."
  type        = string
}
variable "environment" {
  description = "Environment tier (dev|staging|prod)."
  type        = string
}
variable "vpc_id" {
  description = "Existing VPC to run the cluster in."
  type        = string
}
variable "subnet_ids" {
  description = "Private subnets for nodes + control plane ENIs."
  type        = list(string)
}
variable "cluster_version" {
  description = "Kubernetes minor version."
  type        = string
}
variable "node_instance_type" {
  description = "EC2 type for the managed node group."
  type        = string
}
variable "node_min_size" {
  description = "Minimum nodes."
  type        = number
}
variable "node_max_size" {
  description = "Maximum nodes."
  type        = number
}
variable "kms_key_arn" {
  description = "CMK for envelope-encrypting secrets."
  type        = string
}
variable "public_access_cidrs" {
  description = "CIDRs allowed to reach the API server."
  type        = list(string)
}
variable "tags" {
  description = "Mandatory org tags."
  type        = map(string)
}
