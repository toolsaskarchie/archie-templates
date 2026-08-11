locals {
  # Same Archie page the ECS/ALB path serves — one branded landing for every
  # web-facing entrypoint, whichever cloud or runtime it lands on.
  demo_page = templatefile("${path.module}/../../shared/demo-page.html.tftpl", {
    page_title   = "${var.project} · ${var.environment}"
    button_color = "#3B82F6"
    message      = "9 resources. 10 config fields. One click."
    cloud        = var.cloud
    environment  = var.environment
    served_by    = "Kubernetes Ingress → Deployment"
  })
}

resource "kubernetes_namespace_v1" "main" {
  metadata {
    name   = var.namespace
    labels = var.labels
  }
}

resource "kubernetes_config_map_v1" "page" {
  metadata {
    name      = "${var.project}-page"
    namespace = kubernetes_namespace_v1.main.metadata[0].name
    labels    = var.labels
  }
  data = { "index.html" = local.demo_page }
}

resource "kubernetes_deployment_v1" "main" {
  metadata {
    name      = var.project
    namespace = kubernetes_namespace_v1.main.metadata[0].name
    labels    = var.labels
  }
  spec {
    replicas = var.replicas
    selector {
      match_labels = { app = var.project }
    }
    template {
      metadata {
        labels      = merge(var.labels, { app = var.project })
        annotations = { "archie.io/page-hash" = sha1(local.demo_page) }
      }
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
            requests = {
              cpu    = var.cpu_request,
              memory = var.memory_request
            }
            limits = {
              cpu    = var.cpu_limit,
              memory = var.memory_limit
            }
          }
          security_context {
            allow_privilege_escalation = false
            read_only_root_filesystem  = true
            capabilities { drop = ["ALL"] }
          }
          liveness_probe {
            http_get {
              path = "/"
              port = var.container_port
            }
            initial_delay_seconds = 10
          }
          readiness_probe {
            http_get {
              path = "/"
              port = var.container_port
            }
            initial_delay_seconds = 5
          }

          volume_mount {
            name       = "page"
            mount_path = "/usr/share/nginx/html"
            read_only  = true
          }
          volume_mount {
            name       = "nginx-conf"
            mount_path = "/etc/nginx/conf.d"
          }
          # read_only_root_filesystem is on, so nginx needs writable scratch.
          volume_mount {
            name       = "cache"
            mount_path = "/var/cache/nginx"
          }
          volume_mount {
            name       = "run"
            mount_path = "/var/run"
          }
        }

        volume {
          name = "page"
          config_map {
            name = kubernetes_config_map_v1.page.metadata[0].name
          }
        }
        volume {
          name = "nginx-conf"
          config_map {
            name = kubernetes_config_map_v1.nginx_conf.metadata[0].name
          }
        }
        volume {
          name = "cache"
          empty_dir {}
        }
        volume {
          name = "run"
          empty_dir {}
        }
      }
    }
  }
}

resource "kubernetes_config_map_v1" "nginx_conf" {
  metadata {
    name      = "${var.project}-nginx-conf"
    namespace = kubernetes_namespace_v1.main.metadata[0].name
    labels    = var.labels
  }
  # Unprivileged container cannot bind :80, so serve on the app port directly.
  data = {
    "default.conf" = <<-CONF
      server {
        listen ${var.container_port};
        location / { root /usr/share/nginx/html; index index.html; }
      }
    CONF
  }
}

resource "kubernetes_service_v1" "main" {
  metadata {
    name      = var.project
    namespace = kubernetes_namespace_v1.main.metadata[0].name
    labels    = var.labels
  }
  spec {
    selector = { app = var.project }
    port {
      port        = 80
      target_port = var.container_port
    }
    type = var.service_type
  }
}

resource "kubernetes_network_policy_v1" "default_deny" {
  metadata {
    name      = "${var.project}-default-deny"
    namespace = kubernetes_namespace_v1.main.metadata[0].name
  }
  spec {
    pod_selector {}
    policy_types = ["Ingress"]

    # Deny everything EXCEPT the port this app serves on. A bare deny-all with no
    # rule blocks the load balancer too, so the page this module exists to
    # publish would be unreachable the moment NetworkPolicy is actually enforced
    # — silently, because EKS's VPC CNI ignores policy unless enabled, so it
    # would work until the day someone turned enforcement on.
    ingress {
      ports {
        port     = var.container_port
        protocol = "TCP"
      }
    }
  }
}

# OPTIONAL ALB Ingress, off by default. The claim that this matched the
# eks-k8s-demo was wrong: that demo exposes a LoadBalancer Service and reads its
# ELB hostname. This path needs the AWS Load Balancer Controller, which nothing
# here installs, so it is gated behind ingress_enabled rather than assumed.
resource "kubernetes_ingress_v1" "main" {
  count = var.ingress_enabled ? 1 : 0
  metadata {
    name      = var.project
    namespace = kubernetes_namespace_v1.main.metadata[0].name
    labels    = var.labels
    annotations = {
      "alb.ingress.kubernetes.io/scheme"           = var.ingress_scheme
      "alb.ingress.kubernetes.io/target-type"      = "ip"
      "alb.ingress.kubernetes.io/listen-ports"     = "[{\"HTTP\":80}]"
      "alb.ingress.kubernetes.io/healthcheck-path" = "/"
    }
  }

  spec {
    ingress_class_name = "alb"

    rule {
      host = var.ingress_host != "" ? var.ingress_host : null
      http {
        path {
          path      = "/"
          path_type = "Prefix"
          backend {
            service {
              name = kubernetes_service_v1.main.metadata[0].name
              port {
                number = 80
              }
            }
          }
        }
      }
    }
  }
}
