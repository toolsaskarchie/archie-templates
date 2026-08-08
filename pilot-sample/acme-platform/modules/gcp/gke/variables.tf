variable "project" {
  description = "Application/product identifier."
  type        = string
}
variable "environment" {
  description = "Environment tier (dev|staging|prod)."
  type        = string
}
variable "project_id" {
  description = "GCP project id."
  type        = string
}
variable "region" {
  description = "GCP region."
  type        = string
}
variable "network_id" {
  description = "Existing VPC."
  type        = string
}
variable "subnet_id" {
  description = "Existing subnet for nodes."
  type        = string
}
variable "machine_type" {
  description = "Node machine type."
  type        = string
}
variable "min_node_count" {
  description = "Autoscaler minimum per zone."
  type        = number
}
variable "max_node_count" {
  description = "Autoscaler maximum per zone."
  type        = number
}
variable "labels" {
  description = "Mandatory org labels."
  type        = map(string)
}
