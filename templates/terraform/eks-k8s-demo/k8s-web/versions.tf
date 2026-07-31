terraform {
  required_version = ">= 1.5"
  required_providers {
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = ">= 2.30"
    }
  }
}

# The target cluster's kubeconfig is supplied by Archie as this deploy's
# Kubernetes cloud-account credentials, so the provider needs no inline config.
provider "kubernetes" {}
