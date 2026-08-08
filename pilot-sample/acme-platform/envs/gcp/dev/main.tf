terraform {
  required_version = ">= 1.6"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
  backend "gcs" {
    bucket = "acme-tfstate-dev"
    prefix = "platform/gcp/dev"
  }
}

provider "google" {
  project = var.project_id
  region  = "us-central1"
}

variable "project_id" {
  description = "GCP project id for this environment."
  type        = string
}

locals {
  project = "acme-platform"
  common_labels = {
    project             = local.project
    environment         = "dev"
    owner               = "platform-engineering"
    cost_center         = "CC-1001"
    managed_by          = "terraform"
    data_classification = "internal"
  }
}

module "network" {
  source      = "../../../modules/gcp/network"
  project     = local.project
  environment = "dev"
  project_id  = var.project_id
  region      = "us-central1"
  subnet_cidr = "10.50.0.0/16"
  labels      = local.common_labels
}

module "gke" {
  source         = "../../../modules/gcp/gke"
  project        = local.project
  environment    = "dev"
  project_id     = var.project_id
  region         = "us-central1"
  network_id     = module.network.network_id
  subnet_id      = module.network.subnet_id
  machine_type   = "e2-standard-2"
  min_node_count = 1
  max_node_count = 3
  labels         = local.common_labels
}

module "data" {
  source                = "../../../modules/gcp/data"
  project               = local.project
  environment           = "dev"
  project_id            = var.project_id
  region                = "us-central1"
  network_id            = module.network.network_id
  tier                  = "db-custom-2-7680"
  availability_type     = "ZONAL"
  backup_retention_days = 7
  deletion_protection   = false
  labels                = local.common_labels
}

module "cache" {
  source         = "../../../modules/gcp/cache"
  project        = local.project
  environment    = "dev"
  project_id     = var.project_id
  region         = "us-central1"
  network_id     = module.network.network_id
  memory_size_gb = 1
  tier           = "BASIC"
  labels         = local.common_labels
}
