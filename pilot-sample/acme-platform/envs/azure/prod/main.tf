terraform {
  required_version = ">= 1.6"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }
  backend "azurerm" {
    resource_group_name  = "acme-tfstate"
    storage_account_name = "acmetfstateprod"
    container_name       = "platform"
    key                  = "azure/prod.tfstate"
  }
}

provider "azurerm" {
  features {}
}

locals {
  project = "acme-platform"
  common_tags = {
    Project            = local.project
    Environment        = "prod"
    Owner              = "platform-engineering"
    CostCenter         = "CC-2002"
    ManagedBy          = "terraform"
    DataClassification = "internal"
  }
}

module "network" {
  source      = "../../../modules/azure/network"
  project     = local.project
  environment = "prod"
  location    = "westeurope"
  vnet_cidr   = "10.41.0.0/16"
  tags        = local.common_tags
}

module "aks" {
  source              = "../../../modules/azure/aks"
  project             = local.project
  environment         = "prod"
  location            = "westeurope"
  resource_group_name = module.network.resource_group_name
  subnet_id           = module.network.private_subnet_id
  kubernetes_version  = "1.30"
  node_vm_size        = "Standard_D8s_v5"
  node_min_count      = 3
  node_max_count      = 9
  tags                = local.common_tags
}

module "data" {
  source                = "../../../modules/azure/data"
  project               = local.project
  environment           = "prod"
  location              = "westeurope"
  resource_group_name   = module.network.resource_group_name
  sku_name              = "GP_Standard_D8s_v3"
  storage_mb            = 131072
  backup_retention_days = 30
  geo_redundant_backup  = true
  high_availability     = true
  tags                  = local.common_tags
}

module "cache" {
  source              = "../../../modules/azure/cache"
  project             = local.project
  environment         = "prod"
  location            = "westeurope"
  resource_group_name = module.network.resource_group_name
  sku_name            = "Premium"
  capacity            = 2
  tags                = local.common_tags
}
