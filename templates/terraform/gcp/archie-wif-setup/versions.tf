terraform {
  required_version = ">= 1.5"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 5.0"
    }
  }
}

# Uses YOUR admin credentials (gcloud ADC or a key you already have) — this is a
# one-time bootstrap you run, not something Archie deploys. Archie itself never
# gets a key; after this, it authenticates keyless via the pool created here.
provider "google" {
  project = var.project_id
}
