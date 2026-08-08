# acme-platform

Multi-cloud platform infrastructure for the Acme customer-facing product.
Standard enterprise layout: reusable modules per cloud, one root per environment.

    modules/aws/{network,data,cache,compute,eks}   VPC, RDS Postgres, ElastiCache, ALB+ECS, EKS
    modules/azure/{network,aks,data,cache}          VNet, AKS, Flexible Server, Redis
    modules/gcp/{network,gke,data,cache}            VPC, GKE, Cloud SQL, Memorystore
    modules/kubernetes/workload                     Namespace, Deployment, Service, NetworkPolicy, Ingress

    envs/aws/{dev,staging,prod}                     us-east-1 / us-east-1 / eu-west-1
    envs/azure/{dev,prod}                           eastus / westeurope
    envs/gcp/{dev,prod}                             us-central1 / europe-west1

## Conventions

Six governance keys on every resource — `Project`, `Environment`, `Owner`,
`CostCenter`, `ManagedBy`, `DataClassification` — as tags on AWS/Azure and as
labels (lowercase, per GCP rules) on GCP and Kubernetes. Naming is
`{project}-{environment}-{resource}` throughout.

Data at rest is encrypted everywhere: AWS via per-environment CMK
`alias/acme-platform-{env}`, GCP via `database_encryption` + `ssl_mode`,
Azure via `minimum_tls_version` and private-only networking. Remote state is
encrypted per cloud (S3 lockfiles, GCS, Azure blob).

Sizing and durability step up by tier. Nothing is internet-facing: ALB ingress is
restricted to corporate CIDRs, EKS/AKS/GKE run private nodes, every data service
is private, and the Kubernetes workload ships a default-deny NetworkPolicy with
non-root, read-only-rootfs containers.

## Running

    cd envs/aws/prod && terraform init && terraform plan -var certificate_arn=...
    cd envs/gcp/prod && terraform init && terraform plan -var project_id=...
