variable "project" {
  description = "Application/product identifier."
  type        = string
}
variable "environment" {
  description = "Environment tier (dev|staging|prod)."
  type        = string
}
variable "namespace" {
  description = "Namespace to deploy into."
  type        = string
}
variable "image" {
  description = "Fully-qualified container image."
  type        = string
}
variable "replicas" {
  description = "Pod replica count."
  type        = number
}
variable "cpu_request" {
  description = "CPU request per pod."
  type        = string
}
variable "memory_request" {
  description = "Memory request per pod."
  type        = string
}
variable "cpu_limit" {
  description = "CPU limit per pod."
  type        = string
}
variable "memory_limit" {
  description = "Memory limit per pod."
  type        = string
}
variable "container_port" {
  description = "Port the app listens on."
  type        = number
  default     = 8080
}
variable "ingress_enabled" {
  description = "Expose via an Ingress."
  type        = bool
}
variable "ingress_host" {
  description = "Hostname for the Ingress."
  type        = string
}
variable "labels" {
  description = "Mandatory org labels."
  type        = map(string)
}
variable "cloud" {
  description = "Cloud this cluster runs on (shown on the demo page)."
  type        = string
  default     = "AWS"
}

variable "ingress_scheme" {
  description = "ALB scheme for the Ingress: internet-facing (public demo) or internal (private)."
  type        = string
  default     = "internet-facing"
}
