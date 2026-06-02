# Archie Test Panel

Blueprints for E2E lifecycle testing across all clouds, engines, credential
types, and environments. Imported into the `archie-e2e-testing` tenant via
Import from Git.

## Why this exists

The main `templates/` tree is the public Starter Library — production-grade
references for new customers. This panel exists alongside it for one purpose:
**every Archie lifecycle phase must work end-to-end on every engine × cloud
combo**, and we need stable, predictable, low-cost blueprints to test against
without polluting the public catalog.

Each blueprint here is:
- Cheap (deploys under 5 min, costs under $5/day)
- Predictable (same field names, same lock vocabulary, same drift surface)
- Honest about what's testable (drift-injectable fields documented per blueprint)

## Phase 1 — Compute (this PR)

| # | Path                                       | Engine | Cloud  | Status |
|---|--------------------------------------------|--------|--------|--------|
| 1 | aws/terraform/lambda-function              | TF     | AWS    | ready  |
| 2 | aws/pulumi/lambda-function                 | Pulumi | AWS    | ready  |
| 3 | azure/terraform/function-app               | TF     | Azure  | ready  |
| 4 | azure/pulumi/function-app                  | Pulumi | Azure  | ready  |
| 5 | gcp/pulumi/cloud-function                  | Pulumi | GCP    | ready  |

## Phases 2-4 (deferred)

- Phase 2: storage + static sites (S3+CF, Azure Static Web, GCS+CDN)
- Phase 3: databases (RDS, Azure SQL, Cloud SQL)
- Phase 4: networking + ALB

## Import order (Greg)

1. Create tenant `archie-e2e-testing` (or reuse existing)
2. For each blueprint:
   - Import from Git pointing at this subfolder
   - In the Blueprint Editor, configure two profiles per the blueprint's README:
     - **Non-prod** — small, cheap, no conditional features
     - **Production** — full features, larger sizing
   - Apply lock_reasons from the GOV/OPS/SEC vocabulary (see per-blueprint README)
   - Publish v1.0.0
3. Run full lifecycle on each: deploy → drift clean → drift inject →
   drift detect → remediate → upgrade (v1.0.1) → rollback → destroy
4. Verify cloud is clean post-destroy

## Lock-reason vocabulary

| Code     | When to use                                          |
|----------|------------------------------------------------------|
| GOV-001  | Feature not required for nonprod                     |
| GOV-002  | Maximum X allowed in nonprod (capacity / cost cap)   |
| OPS-001  | Retention / backup policy                            |
| OPS-002  | Operational invariant (region, account, etc.)        |
| SEC-001  | Security requirement for production                  |
| SEC-002  | Compliance-mandated value (PCI / HIPAA / SOC2)       |

## Tag invariant

Every resource in every blueprint carries:
```
ManagedBy   = "Archie"
Environment = var.environment   (or pulumi env)
Project     = var.project_name
```

This is the contract the orphan scanner + tag-conditional IAM policies rely
on. Don't strip it.
