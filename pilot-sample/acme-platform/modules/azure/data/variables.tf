variable "project"     { description = "Application/product identifier."      type = string }
variable "environment" { description = "Environment tier (dev|staging|prod)." type = string }
variable "location"    { description = "Azure region."                        type = string }
variable "resource_group_name" { description = "Existing resource group."     type = string }
variable "sku_name"    { description = "Flexible Server SKU."                 type = string }
variable "storage_mb"  { description = "Storage in MB."                       type = number }
variable "backup_retention_days" { description = "Backup retention."          type = number }
variable "geo_redundant_backup"  { description = "Geo-redundant backups."     type = bool }
variable "high_availability"     { description = "Zone-redundant HA."         type = bool }
variable "tags"        { description = "Mandatory org tags."                  type = map(string) }
