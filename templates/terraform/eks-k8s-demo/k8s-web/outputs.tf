output "website_url" {
  description = "Public URL of the demo website (ELB hostname; populated once the load balancer is provisioned)"
  value       = try("http://${kubernetes_service.web.status[0].load_balancer[0].ingress[0].hostname}", "pending")
}
output "namespace" {
  description = "Namespace the website runs in"
  value       = kubernetes_namespace.demo.metadata[0].name
}
