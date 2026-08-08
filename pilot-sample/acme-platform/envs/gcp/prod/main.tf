terraform {
  required_version = ">= 1.6"
  required_providers { google = { source = "hashicorp/google" version = "~> 5.0" } }
  backend "gcs" {
    bucket = "acme-tfstate-prod"
    prefix = "platform/gcp/prod"
  }
}

provider "google" {
  project = var.project_id
  region  = "europe-west1"
}

variable "project_id" { description = "GCP project id for this environment." type = string }

locals {
  project = "acme-platform"
  common_labels = {
    project             = local.project
    environment         = "prod"
    owner               = "platform-engineering"
    cost_center         = "CC-2002"
    managed_by          = "terraform"
    data_classification = "internal"
  }
}

module "network" {
  source      = "../../../modules/gcp/network"
  project     = local.project
  environment = "prod"
  project_id  = var.project_id
  region      = "europe-west1"
  subnet_cidr = "10.51.0.0/16"
  labels      = local.common_labels
}

module "gke" {
  source         = "../../../modules/gcp/gke"
  project        = local.project
  environment    = "prod"
  project_id     = var.project_id
  region         = "europe-west1"
  network_id     = module.network.network_id
  subnet_id      = module.network.subnet_id
  machine_type   = "n2-standard-8"
  min_node_count = 3
  max_node_count = 9
  labels         = local.common_labels
}

module "data" {
  source                = "../../../modules/gcp/data"
  project               = local.project
  environment           = "prod"
  project_id            = var.project_id
  region                = "europe-west1"
  network_id            = module.network.network_id
  tier                  = "db-custom-8-30720"
  availability_type     = "REGIONAL"
  backup_retention_days = 30
  deletion_protection   = true
  labels                = local.common_labels
}

module "cache" {
  source         = "../../../modules/gcp/cache"
  project        = local.project
  environment    = "prod"
  project_id     = var.project_id
  region         = "europe-west1"
  network_id     = module.network.network_id
  memory_size_gb = 5
  tier           = "STANDARD_HA"
  labels         = local.common_labels
}
