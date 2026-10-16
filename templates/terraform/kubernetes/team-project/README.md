# Team Project: Terraform (Kubernetes)

A team's project on a cluster that already exists: the namespaces it deploys into, what it may use there, who may act there, and what Argo CD may sync for it. Only plain Kubernetes objects, so the same module runs on **EKS, GKE and AKS**. Only the cluster Archie points the provider at differs.

Archie adds it to a path when an ask names a team and builds a cluster, or asks for a project or namespace for a team ("un EKS para el equipo de networking", "a namespace for the payments team"). It installs after the cluster, and after Argo CD when the path installs Argo CD.

## Resources

- `kubernetes_namespace_v1`: one per namespace (default `team-<team>`), labelled `archie.io/team=<team>`
- `kubernetes_resource_quota_v1`: CPU, memory and pod totals per namespace
- `kubernetes_limit_range_v1`: default requests and limits for containers that set none (a quota refuses those pods otherwise)
- `kubernetes_role_binding_v1`: the team's group gets `group_role` (default `edit`) inside its namespaces only
- `kubernetes_manifest` (Argo CD `AppProject`, when `argocd_project = true`): destinations limited to the team's namespaces, sources limited to `source_repos`, no cluster-scoped objects, and a `team` role for the group

## Variables

| Name | Default | Description |
|---|---|---|
| `team` | (required) | The team; names the namespace, project and default group |
| `namespaces` | `[]` → `["team-<team>"]` | Namespaces the team deploys into |
| `project_name` | `""` → `team-<team>` | Argo CD AppProject name |
| `group` | `""` → `team-<team>` | The team's group as the identity provider names it (SSO/OIDC group) |
| `group_role` | `edit` | ClusterRole bound in each namespace (`view`, `edit`, `admin`) |
| `argocd_project` | `false` | Create the AppProject (needs Argo CD's CRD on the cluster first) |
| `argocd_namespace` | `argocd` | Where Argo CD keeps AppProjects |
| `source_repos` | `[]` | Repos the team's applications may come from; empty = none yet |
| `quota_requests_cpu` / `quota_requests_memory` | `4` / `8Gi` | Total requests per namespace |
| `quota_limits_cpu` / `quota_limits_memory` | `8` / `16Gi` | Total limits per namespace |
| `quota_pods` | `50` | Most pods per namespace |
| `default_request_cpu` / `default_request_memory` | `100m` / `128Mi` | Container default requests |
| `default_limit_cpu` / `default_limit_memory` | `500m` / `512Mi` | Container default limits |
| `labels` | `{}` | Extra labels on every object |

The quota and limit defaults are a starting point. The organisation governs them like any module input, for example by locking `quota_limits_memory` per environment.

## Outputs

`team`, `namespaces`, `namespace` (the first one), `argocd_project` (empty when not created), `group`.

## Importing into Archie

1. Studio → Import → Terraform from Git
2. Repo: `https://github.com/toolsaskarchie/archie-templates`
3. Path: `templates/terraform/kubernetes/team-project`
4. Publish it. A path that asks for a team project then uses it. When the catalog holds none, a platform engineer's compose imports it from this path.
