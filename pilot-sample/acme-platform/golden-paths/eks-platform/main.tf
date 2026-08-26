# A governed Kubernetes platform: an EKS cluster in its own network, with a
# workload running on it.
#
# THIS IS THE COUNTER-EXAMPLE. In August 2026 a plain-language request for
# exactly this — "a governed Amazon EKS (Kubernetes) cluster in a NEW VPC, to
# run a platform stack" — was answered with a single EC2 instance behind a load
# balancer, because a word borrowed from "IAM Roles for Service Accounts"
# matched a published path called "Public Web Service". Every Kubernetes
# requirement vanished silently.
#
# Importing this root is the honest version of that ask: three components, two
# real edges, and a shape nobody can mistake for a web server.

terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.30"
    }
  }
}

provider "aws" {
  region = var.region
  default_tags { tags = local.common_tags }
}

locals {
  project = "acme-platform"
  common_tags = {
    Project            = local.project
    Environment        = var.environment
    Owner              = "platform-engineering"
    CostCenter         = "CC-1001"
    ManagedBy          = "terraform"
    DataClassification = "internal"
  }
}

module "network" {
  source                  = "../../modules/aws/network"
  project                 = local.project
  environment             = var.environment
  region                  = var.region
  vpc_cidr                = var.vpc_cidr
  az_count                = 3
  flow_log_retention_days = 30
  kms_key_arn             = var.kms_key_arn
  tags                    = local.common_tags
}

# The cluster sits in PRIVATE subnets. `public_access_cidrs` governs who may
# reach the control plane API — which is a different question from who may
# reach an application, and the one an org standard should pin.
module "eks" {
  source              = "../../modules/aws/eks"
  project             = local.project
  environment         = var.environment
  vpc_id              = module.network.vpc_id
  subnet_ids          = module.network.private_subnet_ids
  cluster_version     = var.cluster_version
  node_instance_type  = var.node_instance_type
  node_min_size       = var.node_min_size
  node_max_size       = var.node_max_size
  kms_key_arn         = var.kms_key_arn
  public_access_cidrs = var.public_access_cidrs
  tags                = local.common_tags
}

# Authenticated from the cluster the line above created. This provider block is
# why the workload edge is real rather than inferred: it cannot be configured
# until the cluster exists.
provider "kubernetes" {
  host                   = module.eks.cluster_endpoint
  cluster_ca_certificate = base64decode(module.eks.cluster_ca)
  exec {
    api_version = "client.authentication.k8s.io/v1beta1"
    command     = "aws"
    args        = ["eks", "get-token", "--cluster-name", module.eks.cluster_name]
  }
}

module "workload" {
  source          = "../../modules/kubernetes/workload"
  project         = local.project
  environment     = var.environment
  namespace       = "${local.project}-${var.environment}"
  image           = var.image
  replicas        = var.replicas
  cpu_request     = "250m"
  memory_request  = "512Mi"
  cpu_limit       = "1"
  memory_limit    = "1Gi"
  ingress_enabled = true
  ingress_host    = var.ingress_host
  labels = {
    project             = local.project
    environment         = var.environment
    owner               = "platform-engineering"
    managed_by          = "terraform"
    data_classification = "internal"
  }
}

variable "region" {
  description = "AWS region for this stack."
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Deployment tier. Governs node sizing and retention under org policy."
  type        = string
  default     = "nonprod"
}

variable "vpc_cidr" {
  description = "Address space for the network. Allocated per deploy."
  type        = string
}

variable "kms_key_arn" {
  description = "Customer-managed key for secrets at rest and for log encryption."
  type        = string
}

variable "cluster_version" {
  description = "Kubernetes minor version."
  type        = string
  default     = "1.30"
}

variable "node_instance_type" {
  description = "Size of each worker node."
  type        = string
  default     = "t3.large"
}

variable "node_min_size" {
  description = "Smallest the node group may scale to."
  type        = number
  default     = 1
}

variable "node_max_size" {
  description = "Largest the node group may scale to."
  type        = number
  default     = 3
}

variable "public_access_cidrs" {
  description = "Who may reach the cluster's control plane API. Not who may reach the app."
  type        = list(string)
}

variable "image" {
  description = "Container image the workload runs. Supplied by the deployer, never chosen by the platform."
  type        = string
  default     = "public.ecr.aws/nginx/nginx:stable"
}

variable "replicas" {
  description = "How many pods."
  type        = number
  default     = 2
}

variable "ingress_host" {
  description = "Hostname for the ingress. Empty means the load balancer's own name."
  type        = string
  default     = ""
}

output "cluster_name" {
  description = "The EKS cluster this stack created."
  value       = module.eks.cluster_name
}

output "url" {
  description = "Where the workload answers."
  value       = module.workload.url
}

output "namespace" {
  description = "Namespace the workload runs in."
  value       = module.workload.namespace
}

output "vpc_id" {
  description = "The network this stack created."
  value       = module.network.vpc_id
}
