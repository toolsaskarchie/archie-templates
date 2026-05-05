# VNet Only — Terraform (Azure)

Minimal Azure VNet template — Resource Group, VNet, and configurable subnets. ~4 resources, single file, fast to deploy (~30s).

The Azure equivalent of `templates/terraform/aws/vpc-only` — same minimalist Git import demo path, identical governance flow.

## Resources (~4)

- `azurerm_resource_group`
- `azurerm_virtual_network` (single address space)
- `azurerm_subnet` × N (default 2, configurable 1-4)

## Variables

| Name | Default | Description |
|---|---|---|
| `project_name` | `archie-test` | Tag prefix and resource name root |
| `environment` | `dev` | Environment label (used in tags) |
| `location` | `eastus` | Azure region |
| `resource_group_name` | `archie-test-rg` | Resource group name (created by this stack) |
| `vnet_cidr` | `10.0.0.0/16` | VNet CIDR; subnets carved as /24 within |
| `subnet_count` | `2` | Number of subnets (1-4) |

## Outputs

| Name | What |
|---|---|
| `resource_group_name` | Created RG name |
| `vnet_id` | VNet resource ID |
| `vnet_name` | VNet name |
| `subnet_ids` | List of subnet IDs |
| `address_space` | VNet address space (list) |

## Importing into Archie

1. Studio → Import → Terraform from Git
2. Repo: `https://github.com/toolsaskarchie/archie-templates`
3. Path: `templates/terraform/azure/vnet-only`
4. Studio parses `variables.tf`, infers config schema (6 fields), creates a draft blueprint
5. Lock fields if needed (e.g. lock `location` to your approved regions, lock `vnet_cidr` to your IP plan), publish
6. Deploy via UI or agent

## Why VNet-only?

For demos: the full `web-stack` (VNet + AppGW + VM) takes 5+ min to deploy. The vnet-only template:
- Deploys in ~30 seconds
- 4 resources fit on one screen for the audience
- No AppGW cost (~$0.30/hr saved per demo)
- Same governance flow (lock vnet_cidr, lock location, lock subnet_count)
- Same agent flow (chat → blueprint → governed deploy)

For real work: graduate to `web-stack` for full AppGW+VNet, or use this VNet's outputs (subnet_ids) as input to a separate compute stack.

## Local usage

```bash
terraform init
terraform plan -var="project_name=demo"
terraform apply -var="project_name=demo"
```

## Why not AVM?

The official Azure Verified Modules `virtualnetwork` exposes 25+ vars (IPAM, peering, role assignments, diagnostic settings, encryption, locks). Overkill for a demo template — governance editor would surface a wall of fields. This template uses standard `azurerm_virtual_network` with 6 root vars for a clean import + blueprint editor experience. Customers graduate to AVM once they've outgrown this.
