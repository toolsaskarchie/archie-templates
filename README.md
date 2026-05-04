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

Each template is a Python class that extends Archie's `InfrastructureTemplate` base. At deploy time:

1. Platform Engineer publishes the blueprint with locked fields and compliance rules
2. Developer fills out the deploy form — locked fields hidden, defaults pre-filled
3. Archie runs Pulumi preview, checks compliance, shows the plan
4. On confirm, Pulumi applies; Archie tracks state, outputs, drift, costs

The framework code (`InfrastructureTemplate`, `factory`, `cfg()`, governance hooks) lives in the Archie platform itself and is not in this repo.

## Why open

Archie's value isn't in template code — it's in the governance, lifecycle, and agent platform around it. These templates are open so:

- Developers can see what good IaC looks like
- Platform Engineers can fork them as a starting point
- Sales conversations can point to real code, not slideware

## Use them in Archie

Sign up at [app.askarchie.io](https://app.askarchie.io) — these templates ship with every account. Fork, lock fields, set defaults, deploy.

## Use them standalone

These import from Archie's framework (`provisioner.utils.aws.ResourceNamer`, `factory.create()`, etc.) and aren't runnable standalone today. To extract a runnable Pulumi program from any template, copy the resource definitions and wire them into a vanilla Pulumi project — they're regular Pulumi resource calls underneath.

## Contributing

Contributions welcome — open a PR. Templates should follow the [7 framework rules](https://github.com/AskArchie/archie/blob/main/TEMPLATE_FRAMEWORK.md) (link will resolve once the framework is open-sourced).

## License

Apache 2.0 — see LICENSE.
