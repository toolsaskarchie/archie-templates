terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.0"
    }
  }
}

# Provider config is intentionally minimal. The Archie worker injects
# project + credentials via env vars (GOOGLE_PROJECT, GOOGLE_APPLICATION_CREDENTIALS)
# through tf_creds.py - same flow as Azure / AWS.
provider "google" {
}
