# VPC Only — Terraform (GCP)

Minimal GCP VPC template — single VPC network with configurable subnets. ~3 resources, single file, fast to deploy (~30s).

The GCP equivalent of `templates/terraform/aws/vpc-only` and `templates/terraform/azure/vnet-only` — same minimalist Git import demo path, identical governance flow.

## Resources (~3)

- `google_compute_network` (auto_create_subnetworks = false)
- `google_compute_subnetwork` x N (default 2, configurable 1-4)

## Variables

| Name | Default | Description |
|---|---|---|
| `project_name` | `archie-test` | Resource name root (sanitized to RFC1035) |
| `environment` | `dev` | Environment label (used in labels) |
| `region` | `us-central1` | GCP region for the subnets |
| `vpc_cidr` | `10.0.0.0/16` | CIDR block used to derive /24 subnets |
| `subnet_count` | `2` | Number of subnets (1-4) |
| `routing_mode` | `REGIONAL` | Dynamic routing mode (REGIONAL or GLOBAL) |

## Outputs

| Name | What |
|---|---|
| `network_id` | Full VPC resource ID |
| `network_name` | VPC name |
| `network_self_link` | VPC self link URL |
| `subnet_ids` | List of subnet IDs |
| `subnet_self_links` | List of subnet self link URLs |
| `routing_mode` | Configured dynamic routing mode |

## Importing into Archie

1. Studio - Import - Terraform from Git
2. Repo: `https://github.com/toolsaskarchie/archie-templates`
3. Path: `templates/terraform/gcp/vpc-only`
4. Studio parses `variables.tf`, infers config schema (6 fields), creates a draft blueprint
5. Lock fields if needed (e.g. lock `region` to approved regions, lock `routing_mode` to REGIONAL), publish
6. Deploy via UI or agent

## Why VPC-only?

For demos: the full multi-resource GCP stacks take 5+ min to deploy. The vpc-only template:
- Deploys in ~30 seconds
- 3 resources fit on one screen for the audience
- Zero hourly cost (VPCs and subnets are free in GCP)
- Same governance flow (lock routing_mode, lock region, lock subnet_count)
- Same agent flow (chat - blueprint - governed deploy)

For real work: use this VPC's outputs (`network_self_link`, `subnet_self_links`) as input to a separate compute stack.

## Local usage

```bash
export GOOGLE_PROJECT=my-gcp-project
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/sa-key.json
terraform init
terraform plan -var="project_name=demo"
terraform apply -var="project_name=demo"
```

## GCP naming notes

GCP network and subnet names must be RFC1035: lowercase, start with a letter, dashes allowed, max 63 chars. The template auto-sanitizes `project_name` via `lower()` + `replace(_, -)` + `substr(0, 50)` so any user input lands on a valid name.
