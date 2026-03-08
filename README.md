# Archie Templates

Open-source infrastructure templates for the [AskArchie](https://app.askarchie.io) Internal Developer Platform.

## What is AskArchie?

AskArchie is an Internal Developer Platform (IDP) that lets platform engineering teams govern, deploy, and maintain cloud infrastructure at scale. It sits between your teams and your cloud accounts, ensuring every deployment follows your organization's standards.

**AskArchie is not a template provider.** We provide the platform to securely and compliantly deploy infrastructure into your existing AWS, GCP, Azure, and Kubernetes environments. These templates are the building blocks — your platform team forks, locks, and governs them to match your company's standards.

## How it works

```
Archie Base Library (this repo)
        |
        v
  Fork to Company ──> Lock fields, set defaults, add policies
        |
        v
  Publish Blueprint ──> Developers see a clean deploy form
        |
        v
  Deploy with Preview ──> Pulumi runs preview, shows every resource + cost
        |
        v
  Drift Detection ──> Archie catches console changes, reconciles to standard
```

## Template tiers

| Tier | Purpose | Example |
|------|---------|---------|
| **Atomic** | Single cloud resource | EC2 Instance, S3 Bucket, VPC |
| **Standard** | Production-ready stack | VPC + subnets + NAT + flow logs |
| **Group** | Multi-template composition | Full compute (VPC + ALB + EC2 + monitoring) |

## Repository structure

```
provisioner/templates/
  atomic/           # Single-resource templates
    aws/
      compute/      # ec2_atomic, eks_atomic
      database/     # rds_atomic, aurora_cluster_atomic, dynamodb_atomic
      networking/   # vpc_atomic, subnet_atomic, alb_atomic, ...
      iam/          # iam_role_atomic, iam_policy_atomic
      s3/           # basic_bucket
      security/     # secretsmanager_secret_atomic
      storage/      # s3_bucket_atomic, s3_bucket_policy_atomic
    gcp/
      networking/   # vpc_atomic, firewall_atomic, nat_atomic
    azure/
      networking/   # vnet_atomic

  templates/        # Production-ready stacks
    aws/
      compute/      # ec2_nonprod, ec2_prod, eks_nonprod
      database/     # aurora_nonprod, rds_postgres, redis_nonprod
      networking/   # vpc_nonprod, vpc_prod, alb_nonprod
      cdn/          # cloudfront_nonprod
      s3/           # static_website
    gcp/            # compute_nonprod, vpc_nonprod, static_website
    azure/          # container_webapp, static_website
    kubernetes/     # web_app

  groups/           # Multi-template compositions
    aws/            # compute_group, database_group, vpc_group, ...
```

## Template anatomy

Every template consists of:

- **`config.py`** — Declares configurable parameters (instance type, CIDR block, environment, etc.)
- **`pulumi.py`** — Infrastructure definition using the Archie framework (`@template_registry`, `InfrastructureTemplate`)
- **`marketplace-config.json`** (optional) — Metadata for the AskArchie marketplace (description, features, pillars, cost estimates)

Templates use the Archie framework, not raw Pulumi:

```python
from provisioner.templates.base.template import InfrastructureTemplate
from provisioner.templates.shared.registry import template_registry

@template_registry.register("aws-ec2-nonprod")
class Ec2NonProd(InfrastructureTemplate):
    def create_resources(self):
        # VPC, subnets, security groups, EC2 instance, ...
```

## Using templates with AskArchie

1. **Browse** — Explore the template library in the AskArchie catalog
2. **Fork** — Clone a template to your company's blueprint library
3. **Govern** — Lock fields (e.g., encryption = AES-256), set allowed values, add policy reasons
4. **Publish** — Make it available to your developers as a governed blueprint
5. **Deploy** — Developers fill a clean form, run preview, and deploy — guardrails enforced
6. **Monitor** — AskArchie detects drift, tracks compliance, and manages upgrades

## Building your own templates

You can create templates following the same patterns:

1. Pick a tier (atomic, standard, or group)
2. Create a folder under the appropriate cloud/category
3. Implement `config.py` with your parameters
4. Implement `pulumi.py` extending `InfrastructureTemplate`
5. Register with `@template_registry.register("your-template-name")`
6. Publish to AskArchie via Studio (AI-assisted, code editor, or import from Terraform/CloudFormation)

## Well-Architected alignment

Every template is continuously audited against AWS Well-Architected Framework pillars:

- **Security** — Encryption, IAM least-privilege, network isolation
- **Reliability** — Multi-AZ, health checks, automated backups
- **Performance Efficiency** — Right-sized resources, monitoring, auto-scaling
- **Cost Optimization** — Environment-aware sizing, lifecycle policies
- **Operational Excellence** — Tagging, logging, Infrastructure as Code

## Links

- **Platform**: [app.askarchie.io](https://app.askarchie.io)
- **Sandbox**: [sandbox.askarchie.io](https://sandbox.askarchie.io)

## License

These templates are open source. The AskArchie platform that deploys, governs, and monitors them is a commercial product.
