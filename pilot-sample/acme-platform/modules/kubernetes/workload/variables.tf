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
  # This module is not image-agnostic and never was: it mounts a page at
  # /usr/share/nginx/html, a server block at /etc/nginx/conf.d and scratch at
  # /var/cache/nginx. Anything but nginx ignores all three and fails its own
  # readiness probe. Leaving it undefaulted did not keep the choice open, it
  # only made every caller restate the one image that works — dev, staging and
  # prod all pass exactly this.
  default = "public.ecr.aws/nginx/nginx:stable"
}
variable "replicas" {
  description = "Pod replica count."
  type        = number
  # The per-tier values are a platform decision, not this module's: dev runs 2,
  # staging 3, prod 6. The default is the smallest, so a caller that says
  # nothing gets the cheapest thing that runs.
  default = 2
}
variable "cpu_request" {
  description = "CPU request per pod."
  type        = string
  default     = "250m"
}
variable "memory_request" {
  description = "Memory request per pod."
  type        = string
  default     = "512Mi"
}
variable "cpu_limit" {
  description = "CPU limit per pod."
  type        = string
  default     = "1"
}
variable "memory_limit" {
  description = "Memory limit per pod."
  type        = string
  default     = "1Gi"
}
variable "container_port" {
  description = "Port the app listens on."
  type        = number
  default     = 8080
}
variable "ingress_enabled" {
  description = "Expose via an Ingress."
  type        = bool
  # An Ingress is the point — this module exists to put a real ALB in front of
  # the workload rather than a cluster-internal Service. All three environments
  # set it true; none has ever set it false.
  default = true
}
variable "ingress_host" {
  description = "Hostname for the Ingress."
  type        = string
  # Empty is MEANINGFUL, not missing: the rule below reads
  # `host = var.ingress_host != "" ? var.ingress_host : null`, and a null host
  # matches any Host header — which is what makes the ALB's own DNS name work
  # without a DNS record existing first. Setting a hostname here without a
  # matching record makes the app unreachable, so empty is the right default.
  default = ""
}
variable "labels" {
  description = "Mandatory org labels."
  type        = map(string)
  # Which labels are mandatory is the org's call, not this module's, so it holds
  # no opinion — but it must not refuse to run for a caller that has no policy.
  default = {}
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
