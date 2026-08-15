locals {
  # The page is INLINE, not read from a file, because this module has to survive
  # being imported on its own. Archie snapshots a module DIRECTORY — the worker
  # log for this very failure reads "Materialized 3 file(s)" — so
  #
  #   templatefile("${path.module}/../../shared/demo-page.html.tftpl", ...)
  #
  # pointed two levels above anything that existed at apply time: path.module is
  # "." and the file was never copied. Moving the template into this directory
  # would not have helped either, since the importer fetches only .tf/.hcl
  # (_TF_LIST_EXTS) and would have skipped a .tftpl wherever it sat.
  #
  # Same Archie page the ECS/ALB path serves — one branded landing for every
  # web-facing entrypoint, whichever cloud or runtime it lands on.
  demo_page = <<-HTML
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <title>${var.project} · ${var.environment}</title>
      <style>
        body { margin:0; padding:0; background-color:#0B0E14;
               font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
               display:flex; flex-direction:column; justify-content:center; align-items:center;
               min-height:100vh; text-align:center; }
        .message  { color:#F1F5F9; font-weight:bold; font-size:42px; margin-bottom:20px;
                    max-width:80%; line-height:1.2; }
        .subtitle { color:#64748B; font-size:18px; margin-bottom:28px; }
        .meta     { color:#94A3B8; font-size:14px; line-height:1.9; margin-bottom:32px; }
        .meta b   { color:#F1F5F9; font-weight:600; }
        .button   { background-color:#3B82F6; color:white; border:none; padding:12px 24px;
                    font-size:18px; border-radius:8px; cursor:pointer; margin-bottom:20px; }
        .button:hover { opacity:0.9; }
        .footer   { color:#64748B; font-size:14px; }
      </style>
    </head>
    <body>
      <div class="message" id="msg">9 resources. 10 config fields. One click.</div>
      <div class="subtitle">${var.project} · ${var.environment}</div>
      <div class="meta">
        <div>cloud <b>${var.cloud}</b> &nbsp;·&nbsp; environment <b>${var.environment}</b></div>
        <div>served by <b>Kubernetes ${var.service_type} Service</b></div>
      </div>
      <button class="button" id="another">Show me another</button>
      <div class="footer">askarchie.io</div>
      <script>
        // THE BUTTON HAS TO DO WHAT IT SAYS. It used to call
        // window.location.reload() over a STATIC page, so "Show me another"
        // re-served the identical sentence — the Lambda demo rotates ten
        // messages per request and this one looked broken beside it.
        //
        // nginx serves a file, so there is no server-side random.choice to
        // borrow: the list ships with the page and the pick happens here. Same
        // ten lines as the Lambda starter, so the two demos say the same thing.
        var MESSAGES = [
          "Governance in the deploy path, not around it",
          "5 fields instead of 50",
          "Drift detected. One click to fix.",
          "The developer deploys. The PE defines the rules.",
          "Your Terraform stays. We govern on top.",
          "Deploy blocked: unresolved drift. Remediate first.",
          "9 resources. 10 config fields. One click.",
          "The real complexity starts the day after deploy.",
          "Detection is solved. The gap is between detected and fixed.",
          "Describe. Generate. Govern. Deploy."
        ];
        var el = document.getElementById("msg");
        var last = -1;
        function pick() {
          // Never the same one twice running. A random pick that repeats reads
          // as a broken button, which is the bug this is fixing.
          var i = Math.floor(Math.random() * MESSAGES.length);
          if (i === last) { i = (i + 1) % MESSAGES.length; }
          last = i;
          el.textContent = MESSAGES[i];
        }
        document.getElementById("another").addEventListener("click", pick);
        pick();
      </script>
    </body>
    </html>
  HTML
}

locals {
  # NEVER CLAIM A NAMESPACE YOU DID NOT MAKE. This module created its namespace
  # unconditionally, which failed on `default` with
  #
  #     Error: namespaces "default" already exists
  #
  # and would have failed the same way on any namespace another team's workload
  # had already made. The failure is the mild half. Terraform destroys what it
  # creates, so had the apply succeeded, tearing this one app down would have
  # taken the namespace with it — and everything else running inside it. On
  # `default` that is most of the cluster.
  #
  # So: create it when it is ours to create, and otherwise just deploy into it.
  _builtin_namespaces = ["default", "kube-system", "kube-public", "kube-node-lease"]
  create_namespace    = var.create_namespace && !contains(local._builtin_namespaces, var.namespace)

  # Every resource below reads the namespace from HERE, not from the resource.
  # When we create it this carries the dependency; when we do not, there is
  # nothing to depend on because the namespace already exists.
  namespace = local.create_namespace ? kubernetes_namespace_v1.main[0].metadata[0].name : var.namespace
}

resource "kubernetes_namespace_v1" "main" {
  count = local.create_namespace ? 1 : 0

  metadata {
    name   = var.namespace
    labels = var.labels
  }
}

resource "kubernetes_config_map_v1" "page" {
  metadata {
    name      = "${var.project}-page"
    namespace = local.namespace
    labels    = var.labels
  }
  data = { "index.html" = local.demo_page }
}

resource "kubernetes_deployment_v1" "main" {
  metadata {
    name      = var.project
    namespace = local.namespace
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
    namespace = local.namespace
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
    namespace = local.namespace
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
    namespace = local.namespace
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
    namespace = local.namespace
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
