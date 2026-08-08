variable "project" {
  description = "Application/product identifier."
  type        = string
}
variable "environment" {
  description = "Environment tier (dev|staging|prod)."
  type        = string
}
variable "location" {
  description = "Azure region."
  type        = string
}
variable "resource_group_name" {
  description = "Existing resource group."
  type        = string
}
variable "subnet_id" {
  description = "Existing subnet for the node pool."
  type        = string
}
variable "kubernetes_version" {
  description = "AKS version."
  type        = string
}
variable "node_vm_size" {
  description = "VM size for the default node pool."
  type        = string
}
variable "node_min_count" {
  description = "Autoscaler minimum."
  type        = number
}
variable "node_max_count" {
  description = "Autoscaler maximum."
  type        = number
}
variable "tags" {
  description = "Mandatory org tags."
  type        = map(string)
}
