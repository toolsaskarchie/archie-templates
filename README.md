# Archie Templates

Open infrastructure-as-code templates that ship with [AskArchie](https://askarchie.io) — the Agentic Developer Platform.

These are the actual blueprints Archie uses to deploy infrastructure across AWS, Azure, GCP, and Kubernetes. Each one is governed at deploy time (locked fields, compliance checks, drift detection) and managed across its lifecycle (preview → deploy → drift → remediate → upgrade → destroy).

## What's here

| Cloud | Templates |
|-------|-----------|
| AWS | 32 |
| Azure | 20 |
| GCP | 9 |
| Kubernetes | 7 |
| Multi-cloud | 3 |

```
templates/
├── aws/         S3, ALB, EC2, RDS, ECS, EKS, Lambda, VPC, Cognito, Bedrock Agents, etc.
├── azure/       VNet, App Gateway, SQL, Storage, Static Web Apps, Container Apps, etc.
├── gcp/         VPC, Cloud Run, GKE, Cloud SQL, Cloud Storage, etc.
├── kubernetes/  Deployments, Services, Ingress, ConfigMaps, etc.
└── multi/       Cross-cloud composed stacks
```

## How they work

Each template is a Pulumi or Terraform program that uses Archie's helpers for governance, naming, and config plumbing. At deploy time:

1. Platform Engineer publishes the blueprint with locked fields and compliance rules
2. Developer fills out the deploy form — locked fields hidden, defaults pre-filled
3. Archie runs Pulumi preview / Terraform plan, checks compliance, shows the plan
4. On confirm, the engine applies; Archie tracks state, outputs, drift, costs

The framework runs inside the Archie platform — these templates depend on it and aren't designed to run standalone outside an Archie instance.

## Why open

Archie's value isn't in template code — it's in the governance, lifecycle, and agent platform around it. These templates are open so:

- Developers can see what good IaC looks like
- Platform Engineers can fork them as a starting point
- Sales conversations can point to real code, not slideware

## Use them in Archie

Sign up at [app.askarchie.io](https://app.askarchie.io) — these templates ship with every account. Fork, lock fields, set defaults, deploy.

## Use them standalone

These templates use Archie's helpers and aren't runnable standalone outside an Archie instance. To extract a vanilla Pulumi or Terraform program from any template, copy the resource definitions into a fresh project — they're regular Pulumi/TF resource calls underneath the helpers.

## Contributing

Contributions welcome — open a PR. Best place to start is forking an existing template that targets a similar service/cloud, then adapt.

## License

Apache 2.0 — see LICENSE.
