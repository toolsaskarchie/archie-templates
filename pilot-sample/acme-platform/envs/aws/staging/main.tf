terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  backend "s3" {
    bucket       = "acme-tfstate-staging"
    key          = "platform/staging/terraform.tfstate"
    region       = "us-east-1"
    encrypt      = true
    use_lockfile = true
  }
}

provider "aws" {
  region = "us-east-1"
  default_tags { tags = local.common_tags }
}

locals {
  project = "acme-platform"
  common_tags = {
    Project            = local.project
    Environment        = "staging"
    Owner              = "platform-engineering"
    CostCenter         = "CC-1001"
    ManagedBy          = "terraform"
    DataClassification = "internal"
  }
}

data "aws_kms_key" "platform" { key_id = "alias/acme-platform-staging" }

module "network" {
  source                  = "../../../modules/aws/network"
  project                 = local.project
  environment             = "staging"
  region                  = "us-east-1"
  vpc_cidr                = "10.20.0.0/16"
  az_count                = 2
  flow_log_retention_days = 14
  kms_key_arn             = data.aws_kms_key.platform.arn
  tags                    = local.common_tags
}

module "data" {
  source                     = "../../../modules/aws/data"
  project                    = local.project
  environment                = "staging"
  vpc_id                     = module.network.vpc_id
  subnet_ids                 = module.network.private_subnet_ids
  instance_class             = "db.r6g.large"
  multi_az                   = true
  backup_retention_days      = 14
  deletion_protection        = true
  kms_key_arn                = data.aws_kms_key.platform.arn
  allowed_security_group_ids = [module.compute.security_group_id]
  tags                       = local.common_tags
}

module "cache" {
  source                     = "../../../modules/aws/cache"
  project                    = local.project
  environment                = "staging"
  vpc_id                     = module.network.vpc_id
  subnet_ids                 = module.network.private_subnet_ids
  node_type                  = "cache.r6g.large"
  replica_count              = 2
  multi_az_enabled           = true
  snapshot_retention_limit   = 3
  kms_key_arn                = data.aws_kms_key.platform.arn
  allowed_security_group_ids = [module.compute.security_group_id]
  tags                       = local.common_tags
}

module "compute" {
  source             = "../../../modules/aws/compute"
  project            = local.project
  environment        = "staging"
  vpc_id             = module.network.vpc_id
  private_subnet_ids = module.network.private_subnet_ids
  public_subnet_ids  = module.network.public_subnet_ids
  instance_type      = "m5.large"
  desired_count      = 2
  ingress_cidrs      = ["10.0.0.0/8"]
  certificate_arn    = var.certificate_arn
  kms_key_arn        = data.aws_kms_key.platform.arn
  log_retention_days = 14
  tags               = local.common_tags
}

variable "certificate_arn" {
  description = "ACM certificate for the public listener."
  type        = string
}

output "alb_dns_name" {
  description = "Public entrypoint."
  value       = module.compute.alb_dns_name
}
output "vpc_id" {
  description = "Platform VPC."
  value       = module.network.vpc_id
}

module "eks" {
  source              = "../../../modules/aws/eks"
  project             = local.project
  environment         = "staging"
  vpc_id              = module.network.vpc_id
  subnet_ids          = module.network.private_subnet_ids
  cluster_version     = "1.30"
  node_instance_type  = "m5.large"
  node_min_size       = 2
  node_max_size       = 6
  kms_key_arn         = data.aws_kms_key.platform.arn
  public_access_cidrs = ["10.0.0.0/8"]
  tags                = local.common_tags
}

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
  source          = "../../../modules/kubernetes/workload"
  project         = local.project
  environment     = "staging"
  namespace       = "${local.project}-staging"
  image           = "public.ecr.aws/nginx/nginx:stable"
  replicas        = 3
  cpu_request     = "500m"
  memory_request  = "1Gi"
  cpu_limit       = "2"
  memory_limit    = "2Gi"
  ingress_enabled = true
  ingress_host    = ""
  labels = {
    project             = local.project
    environment         = "staging"
    owner               = "platform-engineering"
    managed_by          = "terraform"
    data_classification = "internal"
  }
}

output "eks_cluster_name" {
  description = "EKS cluster."
  value       = module.eks.cluster_name
}
output "workload_namespace" {
  description = "App namespace."
  value       = module.workload.namespace
}
