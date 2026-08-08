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
    storage_account_name = "acmetfstatedev"
    container_name       = "platform"
    key                  = "azure/dev.tfstate"
  }
}

provider "azurerm" {
  features {}
}

locals {
  project = "acme-platform"
  common_tags = {
    Project            = local.project
    Environment        = "dev"
    Owner              = "platform-engineering"
    CostCenter         = "CC-1001"
    ManagedBy          = "terraform"
    DataClassification = "internal"
  }
}

module "network" {
  source      = "../../../modules/azure/network"
  project     = local.project
  environment = "dev"
  location    = "eastus"
  vnet_cidr   = "10.40.0.0/16"
  tags        = local.common_tags
}

module "aks" {
  source              = "../../../modules/azure/aks"
  project             = local.project
  environment         = "dev"
  location            = "eastus"
  resource_group_name = module.network.resource_group_name
  subnet_id           = module.network.private_subnet_id
  kubernetes_version  = "1.30"
  node_vm_size        = "Standard_D2s_v5"
  node_min_count      = 1
  node_max_count      = 3
  tags                = local.common_tags
}

module "data" {
  source                = "../../../modules/azure/data"
  project               = local.project
  environment           = "dev"
  location              = "eastus"
  resource_group_name   = module.network.resource_group_name
  sku_name              = "GP_Standard_D2s_v3"
  storage_mb            = 32768
  backup_retention_days = 7
  geo_redundant_backup  = false
  high_availability     = false
  tags                  = local.common_tags
}

module "cache" {
  source              = "../../../modules/azure/cache"
  project             = local.project
  environment         = "dev"
  location            = "eastus"
  resource_group_name = module.network.resource_group_name
  sku_name            = "Basic"
  capacity            = 1
  tags                = local.common_tags
}
