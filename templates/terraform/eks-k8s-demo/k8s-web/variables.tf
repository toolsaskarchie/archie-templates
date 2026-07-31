variable "environment" {
  description = "Environment name (nonprod, prod)"
  type        = string
  default     = "nonprod"
}
variable "namespace" {
  description = "Kubernetes namespace for the demo website"
  type        = string
  default     = "archie-demo"
}
variable "app_name" {
  description = "Name of the website deployment/service"
  type        = string
  default     = "archie-web"
}
variable "web_replicas" {
  description = "Number of website replicas"
  type        = number
  default     = 2
}
variable "page_title" {
  description = "Title shown on the demo website"
  type        = string
  default     = "Archie EKS & K8s Demo"
}
variable "button_color" {
  description = "Accent colour for the website button"
  type        = string
  default     = "#3B82F6"
}
