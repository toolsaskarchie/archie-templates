# VPC Only — Terraform (AWS)

Minimal AWS VPC template — VPC, public subnets across AZs, Internet Gateway, route table. ~6 resources, single file, fast to deploy (~30s).

Designed as the simplest possible Git import demo: audience reads the whole template in 10 seconds, sees governance applied, deploys it, watches it land in AWS.

## Resources (~6)

- `aws_vpc` (with DNS support)
- `aws_internet_gateway`
- `aws_subnet` × N (default 2, configurable 1-4)
- `aws_route_table` (public)
- `aws_route_table_association` × N

## Variables

| Name | Default | Description |
|---|---|---|
| `project_name` | `archie-test` | Tag prefix and resource name root |
| `environment` | `dev` | Environment label (used in tags) |
| `vpc_cidr` | `10.0.0.0/16` | VPC CIDR; subnets carved as /24 within |
| `subnet_count` | `2` | Number of public subnets (1-4) |

## Outputs

| Name | What |
|---|---|
| `vpc_id` | The created VPC ID |
| `vpc_cidr` | VPC CIDR block |
| `public_subnet_ids` | List of public subnet IDs |
| `internet_gateway_id` | IGW ID |

## Importing into Archie

1. Studio → Import → Terraform from Git
2. Repo: `https://github.com/toolsaskarchie/archie-templates`
3. Path: `templates/terraform/aws/vpc-only`
4. Studio parses `variables.tf`, infers config schema, creates a draft blueprint
5. Lock fields if needed (e.g. lock `vpc_cidr` to your IP plan), publish
6. Deploy via UI or agent

## Why VPC-only?

For demos: the full `web-stack` (VPC + ALB + EC2) takes 5 min to deploy. The vpc-only template:
- Deploys in ~30 seconds
- 6 resources fit on one screen for the audience
- Same governance flow (lock vpc_cidr, lock subnet_count, lock allowed regions)
- Same agent flow (chat → blueprint → governed deploy)
- No NAT Gateway cost ($0.045/hr saved per demo)

For real work: graduate to `web-stack` for full ALB+VPC, or add your own modules on top of this VPC's outputs (the public_subnet_ids are exported for downstream use).

## Local usage

```bash
terraform init
terraform plan -var="project_name=demo"
terraform apply -var="project_name=demo"
```
