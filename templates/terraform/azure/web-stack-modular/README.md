# Web Stack — Terraform (Azure)

Modular Terraform deploying a complete web application stack on Azure. Mirrors the structure of `templates/terraform/aws/web-stack` so the same demo flow works across clouds.

## Layout

```
web-stack/
├── main.tf              # Calls the three modules
├── variables.tf         # Top-level inputs (blueprint config surface)
├── outputs.tf           # Stack outputs (forwarded from modules)
├── versions.tf          # Terraform + AzureRM provider version pins
└── modules/
    ├── vnet/            # VNet + 2 subnets (appgw + backend) + NSGs
    ├── appgw/           # Public IP + Application Gateway + backend pool + listener
    └── vm/              # Linux VM (Ubuntu 22.04) running Apache
```

## Resources (~12 total)

| Module | Resources |
|---|---|
| `vnet` | VNet, 2 subnets, 2 NSGs (one per subnet), 2 NSG associations |
| `appgw` | Public IP (Standard SKU, static), Application Gateway (Standard_v2) with backend pool, HTTP listener, routing rule |
| `vm` | Network interface, Linux VM (Ubuntu 22.04 LTS) with cloud-init Apache install |

Plus root: `azurerm_resource_group`.

## Top-level variables

| Name | Default | Description |
|---|---|---|
| `project_name` | `archie-test` | Tag prefix and resource name root |
| `environment` | `dev` | Environment label (used in tags) |
| `location` | `eastus` | Azure region |
| `resource_group_name` | `archie-test-rg` | Resource group name (created by this stack) |
| `vnet_cidr` | `10.0.0.0/16` | VNet CIDR; subnets carved as /24 within |
| `vm_size` | `Standard_B1s` | Backend VM size |
| `admin_username` | `azureuser` | VM admin username |
| `admin_password` | (default set, sensitive) | VM admin password — **swap to SSH keys for production** |
| `allowed_cidrs` | `["0.0.0.0/0"]` | CIDR blocks allowed to reach the AppGW on port 80 |

## Outputs

| Name | What |
|---|---|
| `resource_group_name` | Created RG name |
| `vnet_id` | VNet resource ID |
| `appgw_id` | Application Gateway resource ID |
| `appgw_public_ip` | Public IP of the AppGW (curl this) |
| `appgw_public_fqdn` | Public FQDN (Azure-assigned) |
| `vm_id` | VM resource ID |
| `vm_private_ip` | VM private IP (in backend subnet) |

## Importing into Archie

1. Studio → Import → Terraform from Git
2. Repo: `https://github.com/toolsaskarchie/archie-templates`
3. Path: `templates/terraform/azure/web-stack`
4. Studio parses root `variables.tf`, infers config schema, creates a draft blueprint
5. Lock fields (e.g. lock `vm_size=Standard_B2s` for prod, lock `vnet_cidr` to your IP plan), set custom defaults, publish
6. The agent + UI can now deploy this stack with governance applied

## Local usage

```bash
terraform init
terraform plan
terraform apply
```

After apply: `curl http://$(terraform output -raw appgw_public_ip)` — should return "Hello from archie-test".

## Why not AVM?

The official Azure Verified Modules (e.g. `Azure/terraform-azurerm-avm-res-network-virtualnetwork`) are excellent for production but expose **25+ variables** with complex object types (IPAM, peering, role assignments, diagnostic settings, encryption, locks). That's overkill for a starter blueprint and creates an unwieldy governance surface.

This template uses the standard `azurerm` provider with a small focused variable set so:
- Blueprint editors stay readable (8 fields vs 25+)
- The 3 module split mirrors the AWS web-stack — same demo flow across clouds
- Customers can graduate to AVM once they've outgrown this template's defaults

## Why modular?

Same reasons as the AWS web-stack:
- **Composability** — the `vnet` module re-uses across other stacks (AKS, AppService, SQL)
- **Testability** — each module unit-tests in isolation with terratest
- **Readability** — root `main.tf` reads as the architecture, not the implementation
- **Governance fit** — Archie's blueprint editor maps cleanly to the root variables; module internals stay private
