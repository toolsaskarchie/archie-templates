// A variable with NO default is what makes an input REQUIRED, and required is
// what Archie composes on: a component's wiring is built from the inputs it
// declares it must be given. The registry ALB module defaults vpc_id to null,
// which is true in Terraform and false in life — an ALB with no VPC does not
// load-balance, it just plans. That module composed with nothing because it
// asked for nothing. vpc_id and public_subnet_ids below have no defaults for
// exactly that reason: they are the edges to the network component.

variable "project" {
  description = "Application/product identifier."
  type        = string
}
variable "environment" {
  description = "Environment tier (dev|staging|prod)."
  type        = string
}
variable "region" {
  description = "AWS region for this stack."
  type        = string
}
variable "vpc_id" {
  description = "VPC the load balancer and its target group live in."
  type        = string
}
variable "public_subnet_ids" {
  description = "Public subnets to place the load balancer in — at least two AZs."
  type        = list(string)
}
variable "allowed_source_cidrs" {
  description = "CIDRs allowed to reach the listener. Named to match the org standard of the same name, so policy fills it and the requester is never asked."
  type        = list(string)
}
variable "tags" {
  description = "Mandatory org tags."
  type        = map(string)
}

// Governed knobs. These carry defaults because the platform team has an answer
// for them and a requester should not be asked — the ticket said "port 80,
// default domain fine for the poc", which is a default, not a decision.
variable "listener_port" {
  description = "Port the load balancer listens on."
  type        = number
  default     = 80
}
variable "internal" {
  description = "Internal (private) load balancer. False = internet-facing."
  type        = bool
  default     = false
}
variable "idle_timeout" {
  description = "Seconds a connection may stay idle."
  type        = number
  default     = 60
}
variable "enable_deletion_protection" {
  description = "Refuse to delete this load balancer. Locked on in production."
  type        = bool
  default     = false
}
variable "target_port" {
  description = "Port registered targets serve on."
  type        = number
  default     = 8080
}
variable "health_check_path" {
  description = "Path the target group probes."
  type        = string
  default     = "/"
}
