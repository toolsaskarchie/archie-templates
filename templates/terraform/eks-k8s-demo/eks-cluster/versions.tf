terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.40"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = ">= 2.30"
    }
  }
}

provider "aws" {
  region = var.region
  default_tags {
    tags = {
      "archie:managed"  = "true"
      "app:name"        = "archie-demo"
      "app:managed-by"  = "terraform"
      environment       = var.environment
    }
  }
}

data "aws_eks_cluster_auth" "this" {
  name = module.eks.cluster_name
}

provider "kubernetes" {
  host                   = module.eks.cluster_endpoint
  cluster_ca_certificate = base64decode(module.eks.cluster_certificate_authority_data)
  token                  = data.aws_eks_cluster_auth.this.token
}
