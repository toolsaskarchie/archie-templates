variable "project"     { description = "Application/product identifier."      type = string }
variable "environment" { description = "Environment tier (dev|staging|prod)." type = string }
variable "project_id"  { description = "GCP project id."                      type = string }
variable "region"      { description = "GCP region."                          type = string }
variable "network_id"  { description = "VPC for private services access."     type = string }
variable "tier"        { description = "Cloud SQL machine tier."              type = string }
variable "availability_type" { description = "ZONAL or REGIONAL."             type = string }
variable "backup_retention_days" { description = "Retained backups."          type = number }
variable "deletion_protection"   { description = "Block accidental deletion." type = bool }
variable "labels"      { description = "Mandatory org labels."                type = map(string) }
