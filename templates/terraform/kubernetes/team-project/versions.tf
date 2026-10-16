terraform {
  required_version = ">= 1.5"
  required_providers {
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = ">= 2.30"
    }
  }
}

# The target cluster's credentials are supplied by Archie for this deploy (the
# cluster the path builds, or the one the workload is bound to), so the
# provider needs no inline config. Plain Kubernetes: the same module on EKS,
# GKE and AKS.
provider "kubernetes" {}
