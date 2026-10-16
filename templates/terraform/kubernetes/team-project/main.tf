# A TEAM'S PROJECT ON A CLUSTER: where the team deploys, what it may use, who
# may do it, and what Argo CD may sync for it. Plain Kubernetes objects, so the
# same module runs on EKS, GKE and AKS.

locals {
  team       = trim(replace(lower(trimspace(var.team)), "/[^a-z0-9-]+/", "-"), "-")
  base       = "team-${local.team}"
  namespaces = length(var.namespaces) > 0 ? var.namespaces : [local.base]
  project    = var.project_name != "" ? var.project_name : local.base
  group      = var.group != "" ? var.group : local.base
  labels = merge(var.labels, {
    "archie.io/team"               = local.team
    "app.kubernetes.io/managed-by" = "archie"
    "app.kubernetes.io/part-of"    = local.project
  })
}

resource "kubernetes_namespace_v1" "team" {
  for_each = toset(local.namespaces)

  metadata {
    name   = each.value
    labels = local.labels
  }
}

resource "kubernetes_resource_quota_v1" "team" {
  for_each = kubernetes_namespace_v1.team

  metadata {
    name      = "team-quota"
    namespace = each.value.metadata[0].name
    labels    = local.labels
  }

  spec {
    hard = {
      "requests.cpu"    = var.quota_requests_cpu
      "requests.memory" = var.quota_requests_memory
      "limits.cpu"      = var.quota_limits_cpu
      "limits.memory"   = var.quota_limits_memory
      "pods"            = var.quota_pods
    }
  }
}

# A quota on requests/limits refuses any pod that sets none, so every container
# gets a default here.
resource "kubernetes_limit_range_v1" "team" {
  for_each = kubernetes_namespace_v1.team

  metadata {
    name      = "team-defaults"
    namespace = each.value.metadata[0].name
    labels    = local.labels
  }

  spec {
    limit {
      type = "Container"
      default_request = {
        cpu    = var.default_request_cpu
        memory = var.default_request_memory
      }
      default = {
        cpu    = var.default_limit_cpu
        memory = var.default_limit_memory
      }
    }
  }
}

resource "kubernetes_role_binding_v1" "team" {
  for_each = kubernetes_namespace_v1.team

  metadata {
    name      = "team-${var.group_role}"
    namespace = each.value.metadata[0].name
    labels    = local.labels
  }

  role_ref {
    api_group = "rbac.authorization.k8s.io"
    kind      = "ClusterRole"
    name      = var.group_role
  }

  subject {
    kind      = "Group"
    name      = local.group
    api_group = "rbac.authorization.k8s.io"
  }
}

# The team's Argo CD project: applications in it may deploy only into the
# team's namespaces, only from the team's repositories, and never create
# cluster-scoped objects. The team's group may manage its own applications.
resource "kubernetes_manifest" "argocd_project" {
  count = var.argocd_project ? 1 : 0

  manifest = {
    apiVersion = "argoproj.io/v1alpha1"
    kind       = "AppProject"
    metadata = {
      name      = local.project
      namespace = var.argocd_namespace
      labels    = local.labels
    }
    spec = {
      description = "Team ${local.team}: its namespaces and repositories only"
      sourceRepos = var.source_repos
      destinations = [for ns in local.namespaces : {
        server    = "https://kubernetes.default.svc"
        namespace = ns
      }]
      clusterResourceWhitelist   = []
      namespaceResourceWhitelist = [{ group = "*", kind = "*" }]
      roles = [{
        name        = "team"
        description = "Members of ${local.group} manage the team's applications"
        policies = [
          "p, proj:${local.project}:team, applications, *, ${local.project}/*, allow",
        ]
        groups = [local.group]
      }]
    }
  }

  depends_on = [kubernetes_namespace_v1.team]
}
