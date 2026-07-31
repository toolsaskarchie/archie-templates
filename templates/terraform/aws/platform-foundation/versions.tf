# -----------------------------------------------------------------------------
# Terraform + provider configuration
# -----------------------------------------------------------------------------
# Providers are pinned; enterprise default tags are applied to every taggable
# resource (mirrors ADR-style org tagging). Public provider only — no vendor
# providers, so `init` never needs an internal credential.
# -----------------------------------------------------------------------------

terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = merge({
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "archie-terraform"
    }, var.tags)
  }
}
