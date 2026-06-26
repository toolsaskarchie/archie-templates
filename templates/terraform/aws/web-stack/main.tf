locals {
  common_tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "Archie"
  }
}

data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_ami" "amazon_linux" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }
}

# ── VPC + networking ───────────────────────────────────────────────────────

resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-${var.environment}-vpc"
  })
}

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-igw"
  })
}

resource "aws_subnet" "public" {
  count                   = 2
  vpc_id                  = aws_vpc.main.id
  cidr_block              = cidrsubnet(var.vpc_cidr, 8, count.index + 1)
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = true

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-public-${count.index}"
    Tier = "public"
  })
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-public-rt"
  })
}

resource "aws_route_table_association" "public" {
  count          = length(aws_subnet.public)
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

# ── ALB-facing SG: open to allowed_cidrs on 80 (+ 443 if HTTPS) ────────────

resource "aws_security_group" "alb" {
  name_prefix = "${var.project_name}-alb-"
  description = "ALB security group - inbound HTTP/HTTPS from allowed CIDRs."
  vpc_id      = aws_vpc.main.id

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

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-alb-sg"
  })

  lifecycle {
    create_before_destroy = true
  }
}

# ── Backend SG: only accepts target_port from the ALB SG ─────────────────

resource "aws_security_group" "backend" {
  name_prefix = "${var.project_name}-backend-"
  description = "Backend security group - only accepts traffic from the ALB SG."
  vpc_id      = aws_vpc.main.id

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

  tags = merge(local.common_tags, {
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

# ── Load Balancer + Target Group ────────────────────────────────────────

resource "aws_lb" "main" {
  name               = local.alb_name
  internal           = var.internal
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = aws_subnet.public[*].id

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-alb"
  })
}

resource "aws_lb_target_group" "main" {
  name     = local.tg_name
  port     = var.target_port
  protocol = "HTTP"
  vpc_id   = aws_vpc.main.id

  health_check {
    enabled             = true
    path                = "/"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 2
    matcher             = "200"
  }

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-tg"
  })
}

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

# ── EC2 backend(s) ─────────────────────────────────────────────────────────
# user_data uses python3 (pre-installed on AL2023) so the backend boots
# with zero internet egress - works in restricted-egress accounts.

resource "aws_instance" "web" {
  count                  = var.ec2_instance_count
  ami                    = data.aws_ami.amazon_linux.id
  instance_type          = var.instance_type
  subnet_id              = aws_subnet.public[count.index % length(aws_subnet.public)].id
  vpc_security_group_ids = [aws_security_group.backend.id]

  user_data = <<-EOF
    #!/bin/bash
    set -euxo pipefail

    # IMDSv2 — proof the lab works: read live instance metadata
    TOKEN=$(curl -s -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 3600")
    META() { curl -s -H "X-aws-ec2-metadata-token: $TOKEN" "http://169.254.169.254/latest/meta-data/$1" || echo unknown; }
    INSTANCE_ID=$(META instance-id)
    INSTANCE_TYPE=$(META instance-type)
    AZ=$(META placement/availability-zone)
    REGION=$(META placement/region)
    PRIVATE_IP=$(META local-ipv4)
    AMI_ID=$(META ami-id)

    # Random Archie message (mirrors the Lambda starter)
    MSG=$(shuf -e \
      "Deploy blocked: unresolved drift. Remediate first." \
      "9 resources. 10 config fields. One click." \
      "The real complexity starts the day after deploy." \
      "Detection is solved. The gap is between detected and fixed." \
      "Describe. Generate. Govern. Deploy." | head -n 1)

    mkdir -p /srv/www
    cat > /srv/www/index.html <<HTML
    <!DOCTYPE html>
    <html lang="en"><head>
      <meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
      <title>${var.project_name}</title>
      <style>
        body{margin:0;background:#0B0E14;color:#F1F5F9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;display:flex;flex-direction:column;justify-content:center;align-items:center;min-height:100vh;text-align:center;padding:2em}
        .message{font-weight:700;font-size:38px;margin-bottom:14px;max-width:80%;line-height:1.2}
        .subtitle{color:#64748B;font-size:18px;margin-bottom:28px}
        .button{background:#7c3aed;color:#fff;border:none;padding:12px 24px;font-size:18px;border-radius:8px;cursor:pointer;margin-bottom:30px}
        .button:hover{opacity:.9}
        .meta{display:grid;grid-template-columns:auto 1fr;gap:6px 18px;font-family:'JetBrains Mono',Menlo,Consolas,monospace;font-size:13px;background:#11161f;padding:18px 24px;border-radius:8px;color:#94a3b8;text-align:left}
        .meta b{color:#cbd5e1;font-weight:500}
        .footer{color:#64748B;font-size:12px;margin-top:28px}
      </style>
    </head><body>
      <div class="message">$MSG</div>
      <div class="subtitle">${var.project_name} | backend instance #${count.index + 1}</div>
      <button class="button" onclick="window.location.reload()">Show me another</button>
      <div class="meta">
        <b>instance_id</b><span>$INSTANCE_ID</span>
        <b>instance_type</b><span>$INSTANCE_TYPE</span>
        <b>az</b><span>$AZ</span>
        <b>region</b><span>$REGION</span>
        <b>private_ip</b><span>$PRIVATE_IP</span>
        <b>ami_id</b><span>$AMI_ID</span>
        <b>served_by</b><span>python3 http.server (no egress required)</span>
      </div>
      <div class="footer">askarchie.io</div>
    </body></html>
    HTML

    cat > /etc/systemd/system/archie-web.service <<'UNIT'
    [Unit]
    Description=Archie demo web server
    After=network.target
    [Service]
    WorkingDirectory=/srv/www
    ExecStart=/usr/bin/python3 -m http.server ${var.target_port}
    Restart=always
    RestartSec=2
    [Install]
    WantedBy=multi-user.target
    UNIT
    systemctl daemon-reload
    systemctl enable --now archie-web.service
  EOF

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-web-${count.index + 1}"
  })
}

resource "aws_lb_target_group_attachment" "web" {
  count            = var.ec2_instance_count
  target_group_arn = aws_lb_target_group.main.arn
  target_id        = aws_instance.web[count.index].id
  port             = var.target_port
}
