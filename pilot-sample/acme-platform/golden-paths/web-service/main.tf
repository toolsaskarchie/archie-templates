# A public web service: instances behind an internet-facing load balancer, in
# their own network, with logs encrypted by a customer-managed key.
#
# The smallest honest version of the shape. Two module blocks, one edge, and
# every value that a platform engineer would govern left as a variable rather
# than hardcoded — so an import can tell what was DECIDED from what was left
# open, which is the distinction a golden path exists to record.

terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.region
  default_tags { tags = local.common_tags }
}

locals {
  project = "acme-platform"
  common_tags = {
    Project            = local.project
    Environment        = var.environment
    Owner              = "platform-engineering"
    CostCenter         = "CC-1001"
    ManagedBy          = "terraform"
    DataClassification = "internal"
  }
}

module "network" {
  source                  = "../../modules/aws/network"
  project                 = local.project
  environment             = var.environment
  region                  = var.region
  vpc_cidr                = var.vpc_cidr
  az_count                = 2
  flow_log_retention_days = 30
  kms_key_arn             = var.kms_key_arn
  tags                    = local.common_tags
}

# Wired from the network's real outputs, not by name. This is the edge the
# import reads: `compute` depends on `network` because it references it.
module "compute" {
  source             = "../../modules/aws/compute"
  project            = local.project
  environment        = var.environment
  vpc_id             = module.network.vpc_id
  private_subnet_ids = module.network.private_subnet_ids
  public_subnet_ids  = module.network.public_subnet_ids
  instance_type      = var.instance_type
  desired_count      = var.desired_count
  ingress_cidrs      = var.ingress_cidrs
  certificate_arn    = var.certificate_arn
  kms_key_arn        = var.kms_key_arn
  log_retention_days = 30
  tags               = local.common_tags
}

variable "region" {
  description = "AWS region for this stack."
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Deployment tier. Governs instance sizing and retention under org policy."
  type        = string
  default     = "nonprod"
}

variable "vpc_cidr" {
  description = "Address space for the network. Allocated per deploy so two instances of this path cannot collide."
  type        = string
}

variable "kms_key_arn" {
  description = "Customer-managed key for logs and volumes at rest."
  type        = string
}

variable "instance_type" {
  description = "Size of each web instance."
  type        = string
  default     = "t3.small"
}

variable "desired_count" {
  description = "How many instances sit behind the load balancer."
  type        = number
  default     = 2
}

variable "ingress_cidrs" {
  description = "Who may reach the load balancer. A public site is meant to be reachable; a private one is not."
  type        = list(string)
}

variable "certificate_arn" {
  description = "ACM certificate for the HTTPS listener."
  type        = string
}

output "url" {
  description = "Where the service answers."
  value       = "https://${module.compute.alb_dns_name}"
}

output "alb_dns_name" {
  description = "Public entrypoint, as a bare host."
  value       = module.compute.alb_dns_name
}

output "vpc_id" {
  description = "The network this stack created."
  value       = module.network.vpc_id
}
