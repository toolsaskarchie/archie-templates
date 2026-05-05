locals {
  common_tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "archie"
  }
}

resource "azurerm_resource_group" "main" {
  name     = var.resource_group_name
  location = var.location
  tags     = local.common_tags
}

module "vnet" {
  source = "./modules/vnet"

  project_name        = var.project_name
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  vnet_cidr           = var.vnet_cidr
  allowed_cidrs       = var.allowed_cidrs
  tags                = local.common_tags
}

module "appgw" {
  source = "./modules/appgw"

  project_name        = var.project_name
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  subnet_id           = module.vnet.appgw_subnet_id
  backend_ip_address  = module.vm.private_ip
  tags                = local.common_tags
}

module "vm" {
  source = "./modules/vm"

  project_name        = var.project_name
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  subnet_id           = module.vnet.backend_subnet_id
  vm_size             = var.vm_size
  admin_username      = var.admin_username
  admin_password      = var.admin_password
  tags                = local.common_tags
}
