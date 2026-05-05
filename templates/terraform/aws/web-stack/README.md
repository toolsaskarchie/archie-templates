# Web Stack — Terraform (AWS)

Flat, single-file Terraform module that deploys a complete web application stack on AWS. Designed as a clean import target for Archie Studio's "Import from Git" flow — bring your existing Terraform into Archie's governed-blueprint flow without rewriting it.

## What it deploys (~15 resources)

- VPC with two public subnets across multiple AZs
- Internet Gateway and route table
- Security group (port 80 inbound, all egress)
- Application Load Balancer with target group + HTTP listener
- EC2 instance (Amazon Linux 2023, configurable type) running Apache
- Target group attachment

## Variables

| Name | Default | Description |
|---|---|---|
| `project_name` | `archie-test` | Tag prefix for all resources |
| `environment` | `dev` | Environment label (used in tags) |
| `instance_type` | `t3.micro` | EC2 instance size |
| `enable_https` | `false` | Reserved for ACM/443 listener (not yet wired) |

## Outputs

| Name | What |
|---|---|
| `vpc_id` | The created VPC ID |
| `alb_dns` | Public ALB DNS name (HTTP) |
| `instance_id` | EC2 instance ID |

## Importing into Archie

1. Studio → Import → Terraform from Git
2. Repo: `https://github.com/toolsaskarchie/archie-templates`
3. Path: `templates/terraform/aws/web-stack`
4. Studio parses `main.tf`, infers config schema from `variable {...}` blocks, and creates a draft blueprint
5. Lock fields, set custom defaults, publish — now governed
