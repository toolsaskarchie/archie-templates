# Platform Foundation — Terraform (GCP)

A governed application landing zone on GCP — VPC, storage, identity, and messaging in one blueprint. The GCP counterpart to the AWS and Azure platform foundations. Essential inputs (`project_name`, `environment`, `gcp_project_id`) have no defaults; governed knobs carry safe defaults and are meant to be locked per policy. Public ingress is rejected by an input validation.

## Resources (~9)

- VPC network with an application subnetwork
- Firewall rule (HTTPS from corporate CIDR only)
- GCS assets bucket with versioning + lifecycle age expiry
- Least-privilege application service account + bucket object-admin binding
- Pub/Sub events topic + subscription
- Random suffix for globally-unique bucket naming

## Variables

| Name | Default | Description |
|---|---|---|
| `project_name` | _(required)_ | Short project/app name; drives all resource naming (3–22 lowercase alnum/hyphen) |
| `environment` | _(required)_ | Deployment environment: `nonprod` or `prod` |
| `gcp_project_id` | `""` | Target GCP project id (empty inherits from deploy credentials) |
| `region` | `us-central1` | GCP region for all resources |
| `subnet_cidr` | `10.30.0.0/24` | CIDR block for the application subnet |
| `allowed_ingress_cidr` | `10.0.0.0/8` | CIDR permitted to reach the app firewall (public rejected) |
| `bucket_versioning_enabled` | `true` | Object versioning on the assets bucket |
| `bucket_age_days` | `90` | Age (days) after which lifecycle deletes objects |
| `pubsub_retention_seconds` | `345600` | Pub/Sub subscription message retention (seconds) |
| `labels` | `{ cost_center = "platform-engineering" }` | Additional labels merged into enterprise defaults |

## Outputs

| Name | What |
|---|---|
| `region` | GCP region this stack deployed into |
| `network_self_link` | Platform VPC self link |
| `subnet_self_link` | Application subnet self link |
| `assets_bucket` | Assets GCS bucket name |
| `events_topic` | Pub/Sub events topic id |
| `app_service_account_email` | Least-privilege application service account email |

## Importing into Archie

1. Studio → Import → Terraform from Git
2. Repo: `https://github.com/toolsaskarchie/archie-templates`
3. Path: `templates/terraform/gcp/platform-foundation`
4. Studio parses `variables.tf`, infers the config schema, creates a draft blueprint
5. Lock fields (region, CIDR, retention), set per-env defaults, publish → governed
6. Deploy via UI or agent
