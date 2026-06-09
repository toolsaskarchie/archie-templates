variable "project_name" {
  description = "Resource name root. Used to derive RFC1035-safe GCP names."
  type        = string
  default     = "archie-test"
}

variable "environment" {
  description = "Environment label (dev, staging, prod). Used in labels."
  type        = string
  default     = "dev"
}

variable "region" {
  description = "GCP region for the subnets."
  type        = string
  default     = "us-central1"
}

variable "vpc_cidr" {
  description = "CIDR block used to carve /24 subnets. Note: GCP VPCs themselves don't take a CIDR — subnets do. This is used only to derive subnet ranges."
  type        = string
  default     = "10.0.0.0/16"
}

variable "subnet_count" {
  description = "Number of subnets to create in the VPC."
  type        = number
  default     = 2
  validation {
    condition     = var.subnet_count >= 1 && var.subnet_count <= 4
    error_message = "subnet_count must be between 1 and 4."
  }
}

variable "routing_mode" {
  description = "Dynamic routing mode for the VPC. REGIONAL keeps routes within their region; GLOBAL shares across regions."
  type        = string
  default     = "REGIONAL"
  validation {
    condition     = contains(["REGIONAL", "GLOBAL"], var.routing_mode)
    error_message = "routing_mode must be REGIONAL or GLOBAL."
  }
}
