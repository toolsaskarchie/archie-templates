variable "region" {
  description = "AWS region for all resources"
  type        = string
  default     = "us-east-1"
}
variable "environment" {
  description = "Environment name (nonprod, prod)"
  type        = string
  default     = "nonprod"
}
variable "cluster_name" {
  description = "Name of the EKS cluster"
  type        = string
  default     = "archie-eks-demo-nonprod"
}
variable "cluster_version" {
  description = "Kubernetes version for the EKS control plane"
  type        = string
  default     = "1.31"
}
variable "vpc_cidr" {
  description = "CIDR block for the platform VPC"
  type        = string
  default     = "10.0.0.0/16"
}
variable "node_instance_types" {
  description = "EC2 instance types for the EKS managed node group"
  type        = list(string)
  default     = ["t3.medium"]
}
variable "node_min_size" {
  description = "Minimum number of nodes in the managed node group"
  type        = number
  default     = 2
}
variable "node_max_size" {
  description = "Maximum number of nodes in the managed node group"
  type        = number
  default     = 4
}
variable "node_desired_size" {
  description = "Desired number of nodes in the managed node group"
  type        = number
  default     = 2
}
variable "cluster_log_types" {
  description = "EKS control plane log types to enable"
  type        = list(string)
  default     = ["api", "audit", "authenticator"]
}
variable "cluster_log_retention_days" {
  description = "CloudWatch log retention in days for cluster logs"
  type        = number
  default     = 30
}
variable "ecr_services" {
  description = "Service names to create ECR repositories for"
  type        = list(string)
  default     = ["web", "api"]
}
