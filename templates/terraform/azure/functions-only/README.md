# Functions Only - Terraform (Azure)

Minimal Azure Functions template - Resource Group, Storage Account, Consumption Plan, Application Insights, and a Linux Function App. ~5 resources, single file, deploys in ~90s.

Companion to `templates/terraform/azure/vnet-only` for serverless coverage in the harness lifecycle.

## Resources (~5)

- `azurerm_resource_group`
- `azurerm_storage_account` (Standard LRS, StorageV2, TLS1_2 min)
- `azurerm_service_plan` (Linux, Y1 Consumption)
- `azurerm_application_insights` (web)
- `azurerm_linux_function_app` (python runtime, ~4 extension)

## Variables

| Name | Default | Description |
|---|---|---|
| `project_name` | `archie-test` | Tag prefix and resource name root; also seeds the unique storage name |
| `environment` | `dev` | Environment label (used in tags) |
| `location` | `eastus` | Azure region |
| `resource_group_name` | `archie-test-rg` | Resource group name (created by this stack) |
| `function_runtime` | `python` | Function runtime stack (only python supported today) |
| `python_version` | `3.11` | Python version for application_stack |
| `storage_tier` | `Standard` | Storage account tier (Standard or Premium) |
| `storage_replication` | `LRS` | Replication: LRS, GRS, RAGRS, ZRS |
| `app_settings` | `{}` | Extra app settings (map of string) merged on top of defaults |

## Outputs

| Name | What |
|---|---|
| `resource_group_name` | Created RG name |
| `function_app_id` | Full Azure resource ID of the function app |
| `function_app_name` | Function app name |
| `function_app_default_hostname` | `<name>.azurewebsites.net` |
| `storage_account_name` | Backing storage account name |
| `app_insights_instrumentation_key` | App Insights key (sensitive) |

## Storage account naming

Azure storage account names are globally unique and limited to 3-24 lowercase alphanumeric characters. This template derives the name deterministically:

```
substr(lower(project_name without non-alphanum), 0, 20) + substr(md5(project_name), 0, 4)
```

So `project_name = "harness-fn-np-abc123"` produces a stable name on every plan/apply.

## Importing into Archie

1. Studio - Import - Terraform from Git
2. Repo: `https://github.com/toolsaskarchie/archie-templates`
3. Path: `templates/terraform/azure/functions-only`
4. Studio parses `variables.tf`, infers config schema (9 fields), creates a draft blueprint
5. Lock fields if needed (e.g. lock `python_version`, lock `storage_replication` to `GRS` in prod), publish
6. Deploy via UI or agent

## Why Functions-only?

For demos and harness coverage: serverless is the Azure-equivalent demo to AWS Lambda. The vnet-only template covers networking; this covers compute. Together they exercise the two big Azure surfaces the harness needs:

- Networking (VNet + subnets) - tag drift + subnet count
- Serverless compute (Function App + storage + plan) - app settings drift + remediate cycle

## Trade-off note

Picked `azurerm_linux_function_app` (modern provider resource, replaces the deprecated `azurerm_function_app`) for cleaner site_config + application_stack blocks. The older 1.x resource is more permissive but produces noisier diffs on every plan due to legacy attributes. Linux Y1 Consumption is the cheapest SKU; promote to EP1 if cold starts matter.

## Local usage

```bash
terraform init
terraform plan -var="project_name=demo"
terraform apply -var="project_name=demo"
```
