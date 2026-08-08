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
variable "subnet_cidr" {
  description = "Primary CIDR for the subnet."
  type        = string
}
variable "labels" {
  description = "Mandatory org labels."
  type        = map(string)
}
