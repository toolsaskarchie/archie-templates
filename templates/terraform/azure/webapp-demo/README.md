# Azure Web App Demo (Terraform)

Linux Python Flask web app on Azure App Service that serves the **same demo HTML** as the AWS Lambda demo. Useful for cross-cloud parity demos: deploy both, hit both URLs, identical UX.

Same "thin dev / fat prod from one blueprint" pattern as the Lambda demo — three boolean toggles gate optional resources so the PE locks one set on the nonprod profile and another on prod.

## Resources

**Always**: Resource Group + Linux App Service Plan + Linux Web App (Python 3.12 + gunicorn) + inline Flask app baked into the deploy zip.

**Conditional**:
- `enable_monitoring=true` → Log Analytics Workspace + Application Insights (auto-instrumented via env vars)
- `enable_staging_slot=true` → Linux Web App deployment slot (blue/green) — **requires S1+ SKU**
- `enable_backup=true` → Storage Account + container + 30-day backup schedule (10-year SAS auto-generated)

## Variables

| Variable | Default | Purpose |
|---|---|---|
| `project_name` | `myapp` | Resource name root + tag prefix |
| `environment` | `dev` | Env label |
| `location` | `eastus` | Azure region |
| `resource_group_name` | _empty_ | Override RG name (defaults to `<project>-<env>-rg`) |
| `sku_name` | `B1` | App Service Plan SKU (F1 free, B1-B3, S1-S3, P0v3-P2v3). Use S1+ to enable staging slot. |
| `python_version` | `3.12` | Runtime version |
| `page_title` | `AskArchie — Cloud Standards Platform` | HTML title + subtitle |
| `button_color` | `#3B82F6` | Refresh button hex color |
| `https_only` | `true` | Force HTTPS |
| `always_on` | `false` | Keep warm (F1 SKU does NOT support — leave false on F1; PE locks true on prod) |
| `enable_monitoring` | `false` | App Insights + Log Analytics |
| `log_retention_days` | `30` | Log Analytics retention (only used when monitoring on) |
| `enable_staging_slot` | `false` | Blue/green deployment slot (needs S1+) |
| `enable_backup` | `false` | Nightly backup to Storage Account |
| `tags` | `{}` | Extra tags merged everywhere |

## Profile story

Same blueprint, two locked profiles set in the governance editor:

| Field | Non-prod (locked) | Prod (locked) |
|---|---|---|
| `sku_name` | `B1` | `S1` |
| `always_on` | `false` | `true` |
| `enable_monitoring` | `false` | `true` |
| `enable_staging_slot` | `false` | `true` |
| `enable_backup` | `false` | `true` |

Resource count: **3 in dev, 7 in prod** (RG + Plan + Web App / + App Insights + Log Analytics + Staging Slot + Storage Account). Same blueprint. One profile toggle.

## Outputs

- `website_url` — Public HTTPS URL
- `web_app_name` / `resource_group_name` / `service_plan_id` / `default_hostname`
- `staging_slot_url` — Slot URL (empty when toggle off)
- `application_insights_connection_string` — sensitive (empty when off)
- `log_analytics_workspace_id` — empty when off
- `backup_storage_account` — empty when off

## Usage

```bash
tofu init
tofu apply -var project_name=archie-demo -var environment=nonprod
curl "$(tofu output -raw website_url)"

# Prod profile
tofu apply \
  -var project_name=archie-demo -var environment=prod \
  -var sku_name=S1 -var always_on=true \
  -var enable_monitoring=true -var enable_staging_slot=true -var enable_backup=true
```

## Mirrors

Pairs 1:1 with [`aws/lambda`](../../aws/lambda) — same env var contract (`PAGE_TITLE`, `BUTTON_COLOR`), same HTML, same random-message rotation, same governance toggle pattern (Lambda has `enable_dlq` / `enable_xray`; Azure has `enable_monitoring` / `enable_staging_slot` / `enable_backup`). Use both to demo Archie governance across clouds.
