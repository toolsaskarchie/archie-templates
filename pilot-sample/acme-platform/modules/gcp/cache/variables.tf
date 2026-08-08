variable "project"     { description = "Application/product identifier."      type = string }
variable "environment" { description = "Environment tier (dev|staging|prod)." type = string }
variable "project_id"  { description = "GCP project id."                      type = string }
variable "region"      { description = "GCP region."                          type = string }
variable "network_id"  { description = "Authorized VPC."                      type = string }
variable "memory_size_gb" { description = "Redis capacity in GiB."            type = number }
variable "tier"        { description = "BASIC or STANDARD_HA."                type = string }
variable "labels"      { description = "Mandatory org labels."                type = map(string) }
