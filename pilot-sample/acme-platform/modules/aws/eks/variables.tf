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
  default     = "1.30"
}

variable "node_ami_type" {
  description = "EKS-optimised AMI family for the node group."
  type        = string
  # AL2023, stated rather than defaulted-into. Leaving ami_type unset means
  # AL2_x86_64 — Amazon Linux 2 — which AWS has retired for 1.30 and up, so the
  # cluster came up and the node group was rejected outright:
  #
  #   CreateNodegroup: InvalidParameterException:
  #   Requested AMI for this version 1.30 is not supported
  #
  # A default that AWS deprecates is a silent expiry date on the module, and it
  # fails AFTER the ~10-minute cluster create, which is the most expensive place
  # to discover it.
  default = "AL2023_x86_64_STANDARD"
}
variable "node_instance_type" {
  description = "EC2 type for the managed node group."
  type        = string
}
variable "node_min_size" {
  description = "Minimum nodes."
  type        = number
  default     = 2
}
variable "node_max_size" {
  description = "Maximum nodes."
  type        = number
  default     = 6
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

variable "log_retention_days" {
  description = "Control-plane log retention. A knob, not a literal — governance can only lock what the module exposes."
  type        = number
  default     = 30
}
