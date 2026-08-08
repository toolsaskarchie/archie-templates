# acme-platform

Platform infrastructure for the Acme customer-facing product. Standard layout:
reusable modules under `modules/`, one root per environment under `envs/`.

    modules/network   VPC, public/private subnets, NAT, flow logs
    modules/data      RDS Postgres (encrypted, IAM auth, private)
    modules/cache     ElastiCache Redis (encrypted at rest + in transit)
    modules/compute   ALB + ECS Fargate service

    envs/dev          us-east-1   10.10.0.0/16
    envs/staging      us-east-1   10.20.0.0/16
    envs/prod         eu-west-1   10.30.0.0/16

## Conventions

Every resource carries `Project`, `Environment`, `Owner`, `CostCenter`,
`ManagedBy`, `DataClassification` via provider `default_tags` plus explicit
module tags. Naming is `{project}-{environment}-{resource}`.

All data at rest uses the per-environment CMK `alias/acme-platform-{env}`.
Remote state is S3 with `encrypt = true` and native lockfiles.

Sizing and durability step up by tier — see each env root. Nothing is
internet-open: ALB ingress is restricted to corporate CIDRs and every data
service is private with security-group-referenced ingress only.

## Running

    cd envs/dev && terraform init && terraform plan -var certificate_arn=...
