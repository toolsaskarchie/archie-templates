# Azure Web App Demo (Terraform)

Linux Python Flask web app on Azure App Service that serves the **same demo HTML** as the AWS Lambda demo. Useful for cross-cloud parity demos: deploy both, hit both URLs, identical UX.

## Resources

- Resource Group
- Linux App Service Plan (default `B1`)
- Linux Web App with Python 3.12 + gunicorn
- Inline Flask app baked into the deploy zip

## Variables

| Variable | Default | Purpose |
|---|---|---|
| `project_name` | `myapp` | Resource name root + tag prefix |
| `environment` | `dev` | Env label |
| `location` | `eastus` | Azure region |
| `resource_group_name` | _empty_ | Override RG name (defaults to `<project>-<env>-rg`) |
| `sku_name` | `B1` | App Service Plan SKU (F1 free, B1 always-on) |
| `python_version` | `3.12` | Runtime version |
| `page_title` | `AskArchie — Cloud Standards Platform` | HTML title + subtitle |
| `button_color` | `#3B82F6` | Refresh button hex color |
| `https_only` | `true` | Force HTTPS |
| `always_on` | `true` | Keep warm (F1 SKU does NOT support — set false on F1) |
| `tags` | `{}` | Extra tags merged everywhere |

## Outputs

- `website_url` — Public HTTPS URL
- `web_app_name` / `resource_group_name` / `service_plan_id` / `default_hostname`

## Usage

```bash
tofu init
tofu apply -var project_name=archie-demo -var environment=nonprod
curl "$(tofu output -raw website_url)"
```

## Mirrors

Pairs 1:1 with [`aws/lambda`](../../aws/lambda) — same env var contract (`PAGE_TITLE`, `BUTTON_COLOR`), same HTML, same random-message rotation. Use both to demo Archie governance across clouds.
