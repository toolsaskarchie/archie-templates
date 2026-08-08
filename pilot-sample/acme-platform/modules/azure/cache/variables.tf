variable "project"     { description = "Application/product identifier."      type = string }
variable "environment" { description = "Environment tier (dev|staging|prod)." type = string }
variable "location"    { description = "Azure region."                        type = string }
variable "resource_group_name" { description = "Existing resource group."     type = string }
variable "sku_name"    { description = "Redis SKU (Basic|Standard|Premium)."  type = string }
variable "capacity"    { description = "Redis cache size unit."               type = number }
variable "tags"        { description = "Mandatory org tags."                  type = map(string) }
