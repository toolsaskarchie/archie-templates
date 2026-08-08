output "namespace" {
  description = "Namespace created."
  value       = kubernetes_namespace_v1.main.metadata[0].name
}
output "service_name" {
  description = "ClusterIP service."
  value       = kubernetes_service_v1.main.metadata[0].name
}

output "alb_hostname" {
  description = "Public ALB hostname provisioned by the AWS Load Balancer Controller."
  value       = var.ingress_enabled ? try(kubernetes_ingress_v1.main[0].status[0].load_balancer[0].ingress[0].hostname, "pending") : null
}
