output "team" {
  description = "The team this project is for, as labelled (archie.io/team)"
  value       = local.team
}

output "namespaces" {
  description = "The team's namespaces"
  value       = [for ns in kubernetes_namespace_v1.team : ns.metadata[0].name]
}

output "namespace" {
  description = "The team's first namespace (where a single workload lands)"
  value       = local.namespaces[0]
}

output "argocd_project" {
  description = "The team's Argo CD AppProject, or empty when it was not created"
  value       = var.argocd_project ? local.project : ""
}

output "group" {
  description = "The group bound in the team's namespaces"
  value       = local.group
}
