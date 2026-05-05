# Web Stack — Terraform (AWS)

Modular Terraform deploying a complete web application stack on AWS. Designed as a clean import target for Archie Studio's "Import from Git" flow — bring your existing modular Terraform into Archie's governed-blueprint workflow without rewriting it.

## Layout

```
web-stack/
├── main.tf              # Calls the three modules in order
├── variables.tf         # Top-level inputs exposed as blueprint config
├── outputs.tf           # Stack outputs (forwarded from modules)
├── versions.tf          # Terraform + AWS provider version pins
└── modules/
    ├── vpc/             # VPC + 2 public subnets + IGW + route table
    │   ├── main.tf
    │   ├── variables.tf
    │   └── outputs.tf
    ├── alb/             # Security group + ALB + target group + listener
    │   ├── main.tf
    │   ├── variables.tf
    │   └── outputs.tf
    └── ec2/             # EC2 instance + target group attachment
        ├── main.tf
        ├── variables.tf
        └── outputs.tf
```

## Resources (~15 total)

| Module | Resources |
|---|---|
| `vpc` | VPC, 2 subnets (public, multi-AZ), IGW, route table, 2 RT associations |
| `alb` | Security group, Application Load Balancer, target group, HTTP listener |
| `ec2` | EC2 instance (Amazon Linux 2023, runs Apache via user_data), target group attachment |

## Top-level variables

| Name | Default | Description |
|---|---|---|
| `project_name` | `archie-test` | Tag prefix and resource name root |
| `environment` | `dev` | Environment label (used in tags) |
| `vpc_cidr` | `10.0.0.0/16` | VPC CIDR; subnets carved as /24 within |
| `instance_type` | `t3.micro` | EC2 instance size |
| `enable_https` | `false` | Reserved for future ACM/443 listener support |
| `allowed_cidrs` | `["0.0.0.0/0"]` | CIDR blocks allowed to reach the ALB |

## Outputs

| Name | What |
|---|---|
| `vpc_id` | The created VPC ID |
| `public_subnet_ids` | List of public subnet IDs |
| `alb_dns` | Public ALB DNS name |
| `alb_arn` | ALB ARN |
| `instance_id` | EC2 instance ID |

## Importing into Archie

1. Studio → Import → Terraform from Git
2. Repo: `https://github.com/toolsaskarchie/archie-templates`
3. Path: `templates/terraform/aws/web-stack`
4. Studio parses the root `variables.tf`, infers config schema from variable definitions, and creates a draft blueprint
5. Lock fields in the Blueprint Editor (e.g. lock `instance_type=t3.micro` for nonprod, lock `vpc_cidr` to match company IP plan), set custom defaults, publish
6. The agent + UI can now deploy this stack with governance applied — locked values override anything the user passes

## Local usage

```bash
terraform init
terraform plan -var="project_name=my-test"
terraform apply -var="project_name=my-test"
```

## Why modular?

Three small reasons + one big one:
- **Composability** — the `vpc` module can be re-used by other stacks (RDS, EKS, ECS variants) without copy-paste
- **Testability** — each module can be unit-tested with terratest in isolation
- **Readability** — root `main.tf` reads as the architecture, not the implementation
- **Governance fit** — Archie's blueprint editor maps cleanly to the root variables; module internals stay out of the user-facing config surface
