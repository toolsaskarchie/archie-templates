# EKS Cluster — Terraform (AWS)

Provisions an EKS cluster (control plane + managed node group + its own VPC) via the upstream `terraform-aws-modules/eks` and `terraform-aws-modules/vpc` registry modules, then bootstraps everything Archie needs to govern workloads on it: per-service ECR repositories, an `archie-deployer` Kubernetes service account with a cluster-admin binding, and a self-contained `kubeconfig` output you register as a Kubernetes cloud account.

This is the **cluster half** of the EKS + Kubernetes demo. Deploy it first, register its `kubeconfig`, then deploy the paired [`k8s-web`](../k8s-web) workload into it.

## Resources (~5 direct + EKS/VPC modules)

- EKS cluster + managed node group (via `module.eks`)
- VPC with public/private subnets (via `module.vpc`)
- ECR repositories per service, each with a lifecycle policy
- `archie-deployer` service account + cluster-role binding + long-lived token secret

## Variables

| Name | Default | Description |
|---|---|---|
| `region` | `us-east-1` | AWS region for all resources |
| `environment` | `nonprod` | Environment name (`nonprod`, `prod`) |
| `cluster_name` | `archie-eks-demo-nonprod` | Name of the EKS cluster |
| `cluster_version` | `1.31` | Kubernetes version for the control plane |
| `vpc_cidr` | `10.0.0.0/16` | CIDR block for the cluster VPC |
| `node_instance_types` | `["t3.medium"]` | Instance types for the managed node group |
| `node_min_size` | `2` | Minimum nodes in the node group |
| `node_max_size` | `4` | Maximum nodes in the node group |
| `node_desired_size` | `2` | Desired nodes in the node group |
| `cluster_log_types` | `["api","audit","authenticator"]` | Control-plane log types to enable |
| `cluster_log_retention_days` | `30` | CloudWatch retention for cluster logs (days) |
| `ecr_services` | `["web","api"]` | Service names to create ECR repositories for |

## Outputs

| Name | What |
|---|---|
| `cluster_name` | EKS cluster name |
| `cluster_endpoint` | EKS cluster API endpoint |
| `cluster_certificate_authority_data` | Base64 cluster CA certificate |
| `vpc_id` | VPC id |
| `ecr_repository_urls` | ECR repository URL per service |
| `kubeconfig` | Self-contained kubeconfig (archie-deployer SA token) to register as a Kubernetes cloud account (sensitive) |

## Importing into Archie

1. Studio → Import → Terraform from Git
2. Repo: `https://github.com/toolsaskarchie/archie-templates`
3. Path: `templates/terraform/eks-k8s-demo/eks-cluster`
4. Studio parses `variables.tf`, infers the config schema, creates a draft blueprint
5. Lock fields (region, cluster version, node sizes), set per-env defaults, publish → governed
6. Deploy via UI or agent, then register the `kubeconfig` output as a Kubernetes cloud account
