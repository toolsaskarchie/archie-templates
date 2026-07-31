# -----------------------------------------------------------------------------
# Terraform + provider configuration (Azure)
# -----------------------------------------------------------------------------
# Public providers only, pinned. azurerm stays on v3 so the storage/versioning
# attribute names are stable.
# -----------------------------------------------------------------------------

terraform {
  required_version = ">= 1.5"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = ">= 3.100"
    }
    random = {
      source  = "hashicorp/random"
      version = ">= 3.5"
    }
  }
}

provider "azurerm" {
  features {}
  # Use the explicit subscription when supplied; otherwise null lets the provider
  # inherit it from the deploy credentials (ARM_SUBSCRIPTION_ID).
  subscription_id = var.azure_subscription_id != "" ? var.azure_subscription_id : null
}
