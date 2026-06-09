# Cloud Function (Gen 2) - Terraform (GCP)

GCP Cloud Functions Gen 2 demo. A tiny HTTP function that returns a JSON greeting, deployed from a bundled Python source archive. Designed as the canonical end-to-end demo for the Archie lifecycle on GCP: import this from Git, govern it, deploy it, drift-check it, remediate it, upgrade it, rollback it, destroy it.

Gen 1 Cloud Functions are deprecated; Gen 2 is the current API and runs on Cloud Run underneath.

## Resources

Always present (3):

- `google_storage_bucket` - holds the zipped source archive (uniform bucket-level access)
- `google_storage_bucket_object` - the actual source archive upload, name keyed on source MD5
- `google_cloudfunctions2_function` - the Cloud Function itself (build_config + service_config)

## Variables

| Name | Default | Description |
|---|---|---|
| `project_name` | `archie-test` | Resource name root (lowered, dash-safe) |
| `environment` | `dev` | Label and suffix on resource names |
| `region` | `us-central1` | GCP region for function + source bucket |
| `runtime` | `python311` | Cloud Function runtime |
| `entry_point` | `hello` | Function name inside `main.py` |
| `memory_mb` | `256` | Memory allocation (128 - 32768) |
| `timeout_seconds` | `60` | Execution timeout (1 - 3600) |
| `min_instances` | `0` | Minimum warm instances (0 = scale to zero) |
| `max_instances` | `3` | Maximum concurrent instances |
| `env_vars` | `{}` | Map of runtime environment variables |

## Outputs

| Name | What |
|---|---|
| `function_url` | Public HTTPS endpoint - hit it in a browser |
| `function_name` | Function name |
| `function_id` | Full GCP resource id |
| `source_bucket_name` | GCS bucket holding the source zip |
| `runtime` / `memory_mb` / `timeout_seconds` / `min_instances` / `max_instances` | Effective config (governance echo) |

## Importing into Archie

1. Studio → **Import & Govern** → Terraform from Git
2. Repo: `https://github.com/toolsaskarchie/archie-templates`
3. Path: `templates/terraform/gcp/cloud-function`
4. Archie parses `variables.tf` and surfaces each as a config field
5. Lock fields per profile - e.g.:
   - **Non-prod profile:** `memory_mb = 256`, `timeout_seconds = 60`, `min_instances = 0`, `max_instances = 3` (cheap, cold-start tolerant)
   - **Production profile:** `memory_mb = 512`, `timeout_seconds = 120`, `min_instances = 1`, `max_instances = 10` (warm, latency budget)
6. Publish → Deploy → open `function_url` in your browser

## Lifecycle demo points

- **Deploy** - 3 resources, ~60s for the first build
- **Drift** - add an env var via the GCP console, run Check Drift, see the diff
- **Remediate** - one click reverts the manual change back to the blueprint value
- **Upgrade** - bump `memory_mb` and republish, then Upgrade the stack
- **Rollback** - pin to prior version, cloud reverts
- **Destroy** - clean teardown, source bucket goes too (force_destroy = true)
