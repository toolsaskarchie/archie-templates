output "namespace" {
  description = "Namespace created."
  value       = kubernetes_namespace_v1.main.metadata[0].name
}
output "service_name" {
  description = "Service name."
  value       = kubernetes_service_v1.main.metadata[0].name
}

output "url" {
  description = "Public URL of the page. ELB hostname from the LoadBalancer Service, or the ALB when the Ingress is enabled."
  value = (
    var.ingress_enabled
    ? try("http://${kubernetes_ingress_v1.main[0].status[0].load_balancer[0].ingress[0].hostname}", "pending")
    : try("http://${kubernetes_service_v1.main.status[0].load_balancer[0].ingress[0].hostname}", "pending")
  )
}

output "alb_hostname" {
  description = "Public ALB hostname provisioned by the AWS Load Balancer Controller."
  value       = var.ingress_enabled ? try(kubernetes_ingress_v1.main[0].status[0].load_balancer[0].ingress[0].hostname, "pending") : null
}
