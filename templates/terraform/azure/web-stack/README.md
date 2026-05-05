# Web Stack — Terraform (Azure)

Single-file Terraform deploying a complete web application stack on Azure (VNet + Application Gateway + Linux VM running Apache). Designed to deploy reliably through the current Pulumi `terraform-module` wrapper.

## Resources (~13)

- Resource Group
- Virtual Network (single address space)
- 2 Subnets (appgw, backend)
- 2 Network Security Groups + associations
- Linux VM (Ubuntu 22.04 LTS) with Apache via cloud-init
- Network Interface
- Public IP (Standard SKU, static)
- Application Gateway (Standard_v2) with backend pool, HTTP listener, routing rule

## Variables

| Name | Default | Description |
|---|---|---|
| `project_name` | `archie-test` | Tag prefix and resource name root |
| `environment` | `dev` | Environment label (used in tags) |
| `location` | `eastus` | Azure region |
| `resource_group_name` | `archie-test-rg` | Created RG name |
| `vnet_cidr` | `10.0.0.0/16` | VNet CIDR |
| `vm_size` | `Standard_B1s` | Backend VM size |
| `admin_username` | `azureuser` | VM admin username |
| `admin_password` | sensitive default | VM password — swap to SSH keys for prod |
| `allowed_cidrs` | `["0.0.0.0/0"]` | CIDR blocks allowed to reach the AppGW |

## Outputs

| Name | What |
|---|---|
| `resource_group_name` | Created RG name |
| `vnet_id` | VNet resource ID |
| `appgw_id` | Application Gateway resource ID |
| `appgw_public_ip` | Public IP of the AppGW (curl this) |
| `appgw_public_fqdn` | Public FQDN |
| `vm_id` | VM resource ID |
| `vm_private_ip` | VM private IP |

## Importing into Archie

1. Studio → Import → Terraform from Git
2. Repo: `https://github.com/toolsaskarchie/archie-templates`
3. Path: `templates/terraform/azure/web-stack`
4. Studio parses `variables.tf`, infers config schema (9 fields), creates a draft blueprint
5. Lock fields if needed, publish, deploy

## Why flat instead of modular?

The current Pulumi `terraform-module` wrapper has a known limitation handling cross-module output references. For modules with output passing (e.g. AppGW backend pool referencing VM private IP from another module), the wrapper provider crashes mid-apply.

**Workaround for now:** ship flat single-file templates. See `templates/terraform/azure/web-stack-modular/` for the production-style modular layout (same resources, organized into `modules/{vnet,appgw,vm}/`).

**Roadmap:** native `terraform apply` path for modular cases — preserves the customer's exact code shape, no flattening, no mutation.
