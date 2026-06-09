# Web Stack — Terraform (AWS)

Single-file Terraform deploying a complete web application stack on AWS. Designed as a clean import target for Archie Studio's "Import from Git" flow that deploys reliably through the current TF wrapper.

## Resources (~13)

- VPC with two public subnets across multiple AZs
- Internet Gateway and route table + route table associations
- Security group (port 80 inbound, all egress)
- Application Load Balancer with target group + HTTP listener
- EC2 instance (Amazon Linux 2023, configurable type) running Apache
- Target group attachment

## Variables

| Name | Default | Description |
|---|---|---|
| `project_name` | `archie-test` | Tag prefix for all resources |
| `environment` | `dev` | Environment label (used in tags) |
| `vpc_cidr` | `10.0.0.0/16` | VPC CIDR; subnets carved as /24 within |
| `instance_type` | `t3.micro` | EC2 instance size |
| `enable_https` | `false` | Reserved for ACM/443 listener (not yet wired) |
| `allowed_cidrs` | `["0.0.0.0/0"]` | CIDR blocks allowed to reach the ALB |

## Outputs

| Name | What |
|---|---|
| `vpc_id` | The created VPC ID |
| `public_subnet_ids` | List of public subnet IDs |
| `alb_dns` | Public ALB DNS name (HTTP) |
| `alb_arn` | ALB ARN |
| `instance_id` | EC2 instance ID |

## Importing into Archie

1. Studio → Import → Terraform from Git
2. Repo: `https://github.com/toolsaskarchie/archie-templates`
3. Path: `templates/terraform/aws/web-stack`
4. Studio parses `variables.tf`, infers config schema, creates a draft blueprint
5. Lock fields, set custom defaults, publish → governed
6. Deploy via UI or agent

## Why flat instead of modular?

The current Pulumi `terraform-module` wrapper has a known limitation handling cross-module output references (e.g. `module.alb.subnet_ids = module.vpc.public_subnet_ids`). For modules nested 1+ levels deep with output passing, the wrapper provider crashes mid-apply with `error reading from server: EOF`.

**Workaround for now:** ship flat single-file templates that deploy reliably through the wrapper. See `templates/terraform/aws/web-stack-modular/` for the production-style modular layout — same resources, organized into `modules/{vpc,alb,ec2}/` — which is what real customer code looks like, but requires a wrapper fix to deploy via Archie.

**Roadmap:** flatten-on-import (Studio resolves `module.X.Y` refs at parse time) OR native `terraform apply` path for modular cases. See `docs/TF_WRAPPER_LIMITATIONS.md` for the analysis.
