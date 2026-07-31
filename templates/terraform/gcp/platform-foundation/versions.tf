# -----------------------------------------------------------------------------
# Terraform + provider configuration (GCP)
# -----------------------------------------------------------------------------
# Public providers only, pinned. The deploy project is an essential input.
# -----------------------------------------------------------------------------

terraform {
  required_version = ">= 1.5"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = ">= 3.5"
    }
  }
}

provider "google" {
  # Use the explicit project when supplied; otherwise null lets the provider inherit
  # the project from the deploy credentials (GOOGLE_PROJECT / the service-account key).
  project = var.gcp_project_id != "" ? var.gcp_project_id : null
  region  = var.region
}
