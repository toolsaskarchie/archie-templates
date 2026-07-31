# K8s Web Workload — Terraform (Kubernetes)

Deploys a small demo website **into an existing Kubernetes cluster** using the `kubernetes` provider — a namespace, a ConfigMap-driven web deployment, and a LoadBalancer service. This is the **workload half** of the EKS + Kubernetes demo: it targets a cluster you already registered as a Kubernetes cloud account (e.g. the one created by the paired [`eks-cluster`](../eks-cluster) blueprint). It provisions no cloud infrastructure of its own.

## Resources (~4)

- Namespace for the demo website
- ConfigMap holding the rendered page
- Deployment (configurable replicas, title, accent colour)
- Service of type LoadBalancer (exposes the website)

## Variables

| Name | Default | Description |
|---|---|---|
| `environment` | `nonprod` | Environment name (`nonprod`, `prod`) |
| `namespace` | `archie-demo` | Kubernetes namespace for the website |
| `app_name` | `archie-web` | Name of the deployment/service |
| `web_replicas` | `2` | Number of website replicas |
| `page_title` | `Archie EKS & K8s Demo` | Title shown on the demo website |
| `button_color` | `#3B82F6` | Accent colour for the website button |

## Outputs

| Name | What |
|---|---|
| `website_url` | Public URL of the demo website (ELB hostname; `pending` until the load balancer is provisioned) |
| `namespace` | Namespace the website runs in |

## Importing into Archie

1. Studio → Import → Terraform from Git
2. Repo: `https://github.com/toolsaskarchie/archie-templates`
3. Path: `templates/terraform/eks-k8s-demo/k8s-web`
4. Studio parses `variables.tf`, infers the config schema, creates a draft blueprint
5. Set per-env defaults (replicas, title), publish → governed
6. Deploy against a registered Kubernetes cloud account (pick the target cluster at deploy time)
