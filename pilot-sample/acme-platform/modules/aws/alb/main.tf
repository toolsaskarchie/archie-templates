locals {
  // An ALB name is capped at 32 characters and rejects anything that is not
  // alphanumeric or a hyphen. project-environment can exceed that on its own,
  // so it is trimmed here rather than at apply, where the failure arrives 90
  // seconds in as an unhelpful ValidationError.
  name = substr(replace("${var.project}-${var.environment}", "/[^a-zA-Z0-9-]/", "-"), 0, 28)
}

resource "aws_security_group" "alb" {
  name        = "${local.name}-alb"
  description = "Ingress for ${var.project} (${var.environment})"
  vpc_id      = var.vpc_id
  tags        = merge(var.tags, { Name = "${local.name}-alb" })
}

resource "aws_vpc_security_group_ingress_rule" "listener" {
  count             = length(var.ingress_cidrs)
  security_group_id = aws_security_group.alb.id
  cidr_ipv4         = var.ingress_cidrs[count.index]
  from_port         = var.listener_port
  to_port           = var.listener_port
  ip_protocol       = "tcp"
  description       = "Allowed by org policy"
}

// Health checks originate FROM the load balancer, so without egress the target
// group never turns healthy and the listener serves 503 to everyone.
resource "aws_vpc_security_group_egress_rule" "all" {
  security_group_id = aws_security_group.alb.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
  description       = "Reach registered targets"
}

resource "aws_lb" "main" {
  name               = local.name
  internal           = var.internal
  load_balancer_type = "application"
  subnets            = var.public_subnet_ids
  security_groups    = [aws_security_group.alb.id]
  idle_timeout       = var.idle_timeout

  enable_deletion_protection = var.enable_deletion_protection
  // Headers Terraform cannot normalise are how request smuggling gets through a
  // load balancer. Dropping them is free and there is no case for keeping them.
  drop_invalid_header_fields = true

  tags = merge(var.tags, { Name = local.name })
}

// Created empty ON PURPOSE. It gives a workload something to register into
// later, and it is what makes this blueprint composable: `target_group_arn` is
// published below, so a service deployed into this app can attach to the load
// balancer that was provisioned for it instead of raising its own.
resource "aws_lb_target_group" "app" {
  name        = "${local.name}-tg"
  port        = var.target_port
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"

  health_check {
    path                = var.health_check_path
    healthy_threshold   = 2
    unhealthy_threshold = 3
    timeout             = 5
    interval            = 15
    matcher             = "200-399"
  }

  tags = merge(var.tags, { Name = "${local.name}-tg" })
}

resource "aws_lb_listener" "main" {
  load_balancer_arn = aws_lb.main.arn
  port              = var.listener_port
  protocol          = "HTTP"

  // The default action answers rather than forwarding, so the load balancer has
  // a live URL the moment it finishes — an empty target group forwards to
  // nothing and returns 503, which looks identical to a broken deploy. Traffic
  // meant for a real service goes to /app*, below.
  default_action {
    type = "fixed-response"
    fixed_response {
      content_type = "text/html"
      status_code  = "200"
      // ALB caps a fixed response at 1024 bytes, so this page is deliberately
      // small and has no external assets — it must render with one request and
      // no egress.
      message_body = <<-EOT
        <!doctype html><meta charset=utf-8><title>${var.project}</title>
        <style>body{margin:0;min-height:100vh;display:grid;place-items:center;
        background:#0B1120;color:#E2E8F0;font:16px/1.6 system-ui,sans-serif}
        main{text-align:center;padding:2rem}h1{margin:0 0 .5rem;font-size:1.8rem}
        p{margin:.2rem 0;color:#94A3B8}b{color:#3B82F6}</style>
        <main><h1>${var.project}</h1>
        <p>Describe. Generate. Govern. Deploy.</p>
        <p><b>Application Load Balancer</b> &middot; ${var.environment} &middot; AWS</p>
        <p>Governed and deployed by Archie.</p></main>
      EOT
    }
  }
}

resource "aws_lb_listener_rule" "app" {
  listener_arn = aws_lb_listener.main.arn
  priority     = 100

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.app.arn
  }

  condition {
    path_pattern { values = ["/app", "/app/*"] }
  }
}
