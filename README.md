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

## Available templates (23)

### AWS (17)
| Template | Category | Complexity | Est. Cost |
|----------|----------|------------|-----------|
| VPC NonProd | Networking | Beginner | $20/mo |
| VPC Prod | Networking | Intermediate | $40/mo |
| ALB NonProd | Networking | Intermediate | $45/mo |
| EC2 NonProd | Compute | Beginner | $10-35/mo |
| EC2 Prod | Compute | Intermediate | $25/mo |
| EKS NonProd | Compute | Advanced | $75/mo |
| RDS PostgreSQL NonProd | Database | Intermediate | $15/mo |
| RDS PostgreSQL Prod | Database | Advanced | $50/mo |
| Aurora NonProd | Database | Advanced | $30/mo |
| DynamoDB Table | Database | Beginner | $1/mo |
| ElastiCache Redis | Database | Intermediate | $15/mo |
| Static Website | Website | Beginner | $0/mo |
| CloudFront CDN | CDN | Intermediate | $5/mo |
| Archie Cross-Account Role | IAM | Beginner | $0/mo |
| Archie Credential Secret | Security | Beginner | $0.40/mo |
| Landing Zone | Governance | Advanced | $10/mo |
| Serverless API | Serverless | Advanced | $5/mo |

### GCP (3)
| Template | Category | Est. Cost |
|----------|----------|-----------|
| Static Website | Website | $0/mo |
| VPC Network | Networking | $5/mo |
| Compute Engine | Compute | $10/mo |

### Azure (2)
| Template | Category | Est. Cost |
|----------|----------|-----------|
| Static Website | Website | $0/mo |
| Container Web App | Compute | $15/mo |

### Kubernetes (1)
| Template | Category | Est. Cost |
|----------|----------|-----------|
| Web App | Compute | Varies |

## Repository structure

```
provisioner/
  templates/
    atomic/           # Single-resource building blocks
      aws/            # 25 atomics (VPC, Subnet, SG, EC2, RDS, S3, IAM, ...)
      gcp/            # 8 atomics (VPC, Subnet, Firewall, NAT, Bucket, ...)
      azure/          # 5 atomics (ResourceGroup, StorageAccount, VNet, ...)
      kubernetes/     # 4 atomics (Deployment, Service, Ingress, ConfigMap)

    templates/        # Production-ready stacks (23 templates)
      aws/
        cdn/          # cloudfront_nonprod
        compute/      # ec2_nonprod, ec2_prod, eks_nonprod
        database/     # aurora_nonprod, dynamodb_table, rds_postgres, rds_postgres_nonprod
        elasticache/  # redis_nonprod
        governance/   # landing_zone
        iam/          # archie_role, archie_secret
        networking/   # alb_nonprod, vpc_nonprod, vpc_prod
        s3/           # static_website
        serverless/   # aws-serverless-api-prod
      azure/          # container_webapp, static_website
      gcp/            # compute/compute_nonprod, networking/vpc_nonprod, static_website
      kubernetes/     # web_app
```

## Building templates

**Read [TEMPLATE_FRAMEWORK.md](TEMPLATE_FRAMEWORK.md)** — the definitive guide for writing Archie templates.

Key rules:
1. **ALL resources through `factory.create()`** — never use direct Pulumi calls
2. **Config class must have**: `self.environment`, `self.region`, `self.tags`, `self.project_name`
3. **All 6 Well-Architected pillars** in `get_metadata()` with `score`, `score_color`, `description`, `practices`
4. **`pulumi.export()`** for all user-relevant outputs
5. **`ResourceNamer`** for all resource naming
6. **Security group tiers**: web (80/443) → app (3000/8080) → db (3306/5432)

## Tools

| Script | Location | Purpose |
|--------|----------|---------|
| `validate-templates.py` | This repo | Validate all templates against TEMPLATE_FRAMEWORK.md |
| `seed-marketplace.py` | This repo | Seed DynamoDB marketplace from template.yaml files |
| `pulumi-extractor.py` | Backend repo (`scripts/new/generate_templates/`) | Scan pulumi.py → generate template.yaml with resources, config, outputs, metadata |

### Development workflow

```
Write pulumi.py + config.py
        ↓
Run pulumi-extractor → generates template.yaml
        ↓
Run validate-templates.py → check compliance
        ↓
Run seed-marketplace.py → push to DynamoDB
        ↓
Test in UI → catalog card, detail, deploy, outputs
```

See [TEMPLATE_FRAMEWORK.md § 13](TEMPLATE_FRAMEWORK.md) for the full workflow with commands.

## Well-Architected alignment

Every template includes all 6 AWS Well-Architected Framework pillars:

- **Operational Excellence** — IaC, monitoring, logging, automated deployments
- **Security** — Encryption, IAM least-privilege, network isolation, SG tiers
- **Reliability** — Multi-AZ, health checks, automated backups, failover
- **Performance Efficiency** — Right-sized resources, caching, auto-scaling
- **Cost Optimization** — Environment-aware sizing, lifecycle policies, reserved capacity
- **Sustainability** — Managed services, right-sizing, efficient resource utilization

## Links

- **Platform**: [app.askarchie.io](https://app.askarchie.io)
- **Landing**: [askarchie.io](https://askarchie.io)
- **Framework Guide**: [TEMPLATE_FRAMEWORK.md](TEMPLATE_FRAMEWORK.md)

## License

These templates are open source. The AskArchie platform that deploys, governs, and monitors them is a commercial product.
