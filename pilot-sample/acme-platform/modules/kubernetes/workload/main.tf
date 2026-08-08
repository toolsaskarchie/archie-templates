resource "kubernetes_namespace" "main" {
  metadata {
    name   = var.namespace
    labels = var.labels
  }
}

resource "kubernetes_deployment" "main" {
  metadata {
    name      = var.project
    namespace = kubernetes_namespace.main.metadata[0].name
    labels    = var.labels
  }
  spec {
    replicas = var.replicas
    selector { match_labels = { app = var.project } }
    template {
      metadata { labels = merge(var.labels, { app = var.project }) }
      spec {
        automount_service_account_token = false
        security_context {
          run_as_non_root = true
          run_as_user     = 10001
          fs_group        = 10001
        }
        container {
          name  = var.project
          image = var.image
          port { container_port = var.container_port }
          resources {
            requests = { cpu = var.cpu_request, memory = var.memory_request }
            limits   = { cpu = var.cpu_limit,   memory = var.memory_limit }
          }
          security_context {
            allow_privilege_escalation = false
            read_only_root_filesystem  = true
            capabilities { drop = ["ALL"] }
          }
          liveness_probe  { http_get { path = "/healthz" port = var.container_port } initial_delay_seconds = 10 }
          readiness_probe { http_get { path = "/readyz"  port = var.container_port } initial_delay_seconds = 5 }
        }
      }
    }
  }
}

resource "kubernetes_service" "main" {
  metadata {
    name      = var.project
    namespace = kubernetes_namespace.main.metadata[0].name
    labels    = var.labels
  }
  spec {
    selector = { app = var.project }
    port { port = 80 target_port = var.container_port }
    type = "ClusterIP"
  }
}

resource "kubernetes_network_policy" "default_deny" {
  metadata {
    name      = "${var.project}-default-deny"
    namespace = kubernetes_namespace.main.metadata[0].name
  }
  spec {
    pod_selector {}
    policy_types = ["Ingress"]
  }
}

resource "kubernetes_ingress_v1" "main" {
  count = var.ingress_enabled ? 1 : 0
  metadata {
    name        = var.project
    namespace   = kubernetes_namespace.main.metadata[0].name
    labels      = var.labels
    annotations = { "kubernetes.io/ingress.class" = "alb", "alb.ingress.kubernetes.io/scheme" = "internal" }
  }
  spec {
    rule {
      host = var.ingress_host
      http {
        path {
          path      = "/"
          path_type = "Prefix"
          backend { service { name = kubernetes_service.main.metadata[0].name port { number = 80 } } }
        }
      }
    }
  }
}
