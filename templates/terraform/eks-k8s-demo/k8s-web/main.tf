locals {
  index_html = <<-HTML
    <!doctype html>
    <html lang="en">
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width,initial-scale=1">
      <title>${var.page_title}</title>
      <style>
        body { margin:0; min-height:100vh; background:#0B0E14; color:#F1F5F9; display:flex; flex-direction:column; align-items:center; justify-content:center; font-family:system-ui,sans-serif; padding:24px; }
        .msg { font-size:42px; font-weight:700; text-align:center; line-height:1.25; max-width:900px; }
        .sub { font-size:18px; color:#64748B; margin-top:24px; text-align:center; }
        .badge { margin-top:28px; font-size:13px; color:#38BDF8; letter-spacing:.5px; text-transform:uppercase; }
        button.btn { margin-top:36px; padding:14px 28px; background:${var.button_color}; color:#fff; border:none; cursor:pointer; border-radius:10px; font-size:18px; font-weight:600; }
        .footer { margin-top:12px; font-size:13px; color:#64748B; }
      </style>
    </head>
    <body>
      <div class="msg" id="msg">Governance in the deploy path, not around it</div>
      <div class="sub">${var.page_title}</div>
      <div class="badge">Live on Amazon EKS &middot; deployed &amp; governed by Archie</div>
      <button class="btn" onclick="pick()">Show me another</button>
      <div class="footer">askarchie.io</div>
      <script>
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
        function pick() {
          var i = Math.floor(Math.random() * MESSAGES.length);
          document.getElementById("msg").textContent = MESSAGES[i];
        }
        pick();
      </script>
    </body>
    </html>
  HTML
}

resource "kubernetes_namespace" "demo" {
  metadata {
    name = var.namespace
    labels = {
      "app.kubernetes.io/part-of"     = "archie-demo"
      "app.kubernetes.io/managed-by"  = "terraform"
      "app.kubernetes.io/environment" = var.environment
    }
  }
}

resource "kubernetes_config_map" "web" {
  metadata {
    name      = "${var.app_name}-html"
    namespace = kubernetes_namespace.demo.metadata[0].name
  }
  data = {
    "index.html" = local.index_html
  }
}

resource "kubernetes_deployment" "web" {
  metadata {
    name      = var.app_name
    namespace = kubernetes_namespace.demo.metadata[0].name
    labels    = { app = var.app_name }
  }

  spec {
    replicas = var.web_replicas

    selector {
      match_labels = { app = var.app_name }
    }

    template {
      metadata {
        labels      = { app = var.app_name }
        annotations = { "archie.io/config-hash" = sha1(local.index_html) }
      }

      spec {
        container {
          name  = "web"
          image = "nginx:1.27-alpine"

          port {
            container_port = 80
          }

          volume_mount {
            name       = "html"
            mount_path = "/usr/share/nginx/html"
            read_only  = true
          }

          resources {
            requests = {
              cpu    = "50m"
              memory = "64Mi"
            }
            limits = {
              cpu    = "200m"
              memory = "128Mi"
            }
          }
        }

        volume {
          name = "html"
          config_map {
            name = kubernetes_config_map.web.metadata[0].name
          }
        }
      }
    }
  }
}

resource "kubernetes_service" "web" {
  metadata {
    name      = var.app_name
    namespace = kubernetes_namespace.demo.metadata[0].name
  }

  spec {
    selector = { app = var.app_name }

    port {
      port        = 80
      target_port = 80
    }

    type = "LoadBalancer"
  }
}
