# Platform Foundation — Terraform (Azure)

A governed application landing zone on Azure — resource group, virtual network, storage, identity, and logging in one blueprint. The Azure counterpart to the AWS and GCP platform foundations. Essential inputs (`project_name`, `environment`) have no defaults; governed knobs carry safe defaults and are meant to be locked per policy. Public ingress is rejected by an input validation.

## Resources (~10)

- Resource group + virtual network with an application subnet
- Network security group + subnet association (corporate-CIDR ingress only)
- Storage account (TLS 1.2 minimum, blob versioning + soft-delete retention) with a blob container
- User-assigned managed identity for the application
- Log Analytics workspace
- Random suffix for globally-unique storage naming

## Variables

| Name | Default | Description |
|---|---|---|
| `project_name` | _(required)_ | Short project/app name; drives all resource naming (3–22 lowercase alnum/hyphen) |
| `environment` | _(required)_ | Deployment environment: `nonprod` or `prod` |
| `azure_subscription_id` | `""` | Target subscription id for the provider |
| `location` | `eastus` | Azure region for all resources |
| `address_space` | `10.20.0.0/16` | CIDR block for the platform virtual network |
| `subnet_prefix` | `10.20.1.0/24` | CIDR block for the application subnet |
| `allowed_ingress_cidr` | `10.0.0.0/8` | CIDR permitted to reach the app NSG (public rejected) |
| `storage_min_tls` | `TLS1_2` | Minimum TLS version on the storage account |
| `blob_versioning_enabled` | `true` | Blob versioning on the assets storage account |
| `blob_retention_days` | `30` | Days to retain soft-deleted blobs (1–365) |
| `log_retention_days` | `30` | Log Analytics workspace retention (30–730) |
| `tags` | `{ CostCenter = "platform-engineering" }` | Additional tags merged into enterprise defaults |

## Outputs

| Name | What |
|---|---|
| `location` | Azure location this stack deployed into |
| `resource_group` | Platform resource group name |
| `vnet_id` | Platform virtual network id |
| `assets_storage_account` | Assets storage account name |
| `log_analytics_workspace_id` | Log Analytics workspace id |
| `app_identity_principal_id` | Application user-assigned identity principal id |

## Importing into Archie

1. Studio → Import → Terraform from Git
2. Repo: `https://github.com/toolsaskarchie/archie-templates`
3. Path: `templates/terraform/azure/platform-foundation`
4. Studio parses `variables.tf`, infers the config schema, creates a draft blueprint
5. Lock fields (location, CIDRs, TLS, retention), set per-env defaults, publish → governed
6. Deploy via UI or agent
