# ── ALB-facing SG: open to allowed_cidrs on 80 + 443 ─────────────────────────

resource "aws_security_group" "alb" {
  name_prefix = "${var.project_name}-alb-"
  description = "ALB security group - inbound HTTP/HTTPS from allowed CIDRs."
  vpc_id      = var.vpc_id

  ingress {
    description = "HTTP from allowed CIDRs"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = var.allowed_cidrs
  }

  dynamic "ingress" {
    for_each = var.enable_https ? [1] : []
    content {
      description = "HTTPS from allowed CIDRs"
      from_port   = 443
      to_port     = 443
      protocol    = "tcp"
      cidr_blocks = var.allowed_cidrs
    }
  }

  egress {
    description = "All outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-alb-sg"
  })

  lifecycle {
    create_before_destroy = true
  }
}

# ── Backend SG: only accepts traffic from the ALB SG on target_port ──────────

resource "aws_security_group" "backend" {
  name_prefix = "${var.project_name}-backend-"
  description = "Backend security group - only accepts traffic from the ALB SG."
  vpc_id      = var.vpc_id

  ingress {
    description     = "Target port from ALB SG only"
    from_port       = var.target_port
    to_port         = var.target_port
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  egress {
    description = "All outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-backend-sg"
  })

  lifecycle {
    create_before_destroy = true
  }
}

locals {
  # ALB / Target Group names cap at 32 chars. Valid short names pass through
  # UNCHANGED (existing stacks keep their name → no destructive ALB replacement
  # on re-apply); long names truncate to 25 + a 6-char sha1 prefix so collisions
  # between similar long project_names stay distinct (#519).
  _alb_raw = "${var.project_name}-alb"
  _tg_raw  = "${var.project_name}-tg"
  alb_name = length(local._alb_raw) <= 32 ? local._alb_raw : "${substr(local._alb_raw, 0, 25)}-${substr(sha1(local._alb_raw), 0, 6)}"
  tg_name  = length(local._tg_raw) <= 32 ? local._tg_raw : "${substr(local._tg_raw, 0, 25)}-${substr(sha1(local._tg_raw), 0, 6)}"
}

# ── Load Balancer ────────────────────────────────────────────────────────────

resource "aws_lb" "main" {
  name               = local.alb_name
  internal           = var.internal
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = var.subnet_ids

  tags = merge(var.tags, {
    Name = "${var.project_name}-alb"
  })
}

# ── Target Group ─────────────────────────────────────────────────────────────

resource "aws_lb_target_group" "main" {
  name     = local.tg_name
  port     = var.target_port
  protocol = "HTTP"
  vpc_id   = var.vpc_id

  health_check {
    enabled             = true
    path                = "/"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 2
    matcher             = "200"
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-tg"
  })
}

# ── Listeners ────────────────────────────────────────────────────────────────

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.main.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.main.arn
  }
}

resource "aws_lb_listener" "https" {
  count = var.enable_https && var.certificate_arn != "" ? 1 : 0

  load_balancer_arn = aws_lb.main.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS-1-2-2017-01"
  certificate_arn   = var.certificate_arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.main.arn
  }
}
