output "namespace"    { description = "Namespace created."  value = kubernetes_namespace.main.metadata[0].name }
output "service_name" { description = "ClusterIP service."  value = kubernetes_service.main.metadata[0].name }
