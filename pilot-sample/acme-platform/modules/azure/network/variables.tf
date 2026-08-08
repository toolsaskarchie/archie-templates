variable "project"     { description = "Application/product identifier."      type = string }
variable "environment" { description = "Environment tier (dev|staging|prod)." type = string }
variable "location"    { description = "Azure region."                        type = string }
variable "vnet_cidr"   { description = "Address space for the VNet."          type = string }
variable "tags"        { description = "Mandatory org tags."                  type = map(string) }
