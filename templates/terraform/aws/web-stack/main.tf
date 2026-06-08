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

# ── Load Balancer + Target Group ────────────────────────────────────────

resource "aws_lb" "main" {
  name               = "${var.project_name}-alb"
  internal           = var.internal
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = aws_subnet.public[*].id

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-alb"
  })
}

resource "aws_lb_target_group" "main" {
  name     = "${var.project_name}-tg"
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
    mkdir -p /srv/www
    cat > /srv/www/index.html <<'HTML'
    <!doctype html>
    <html><head><title>${var.project_name}</title></head>
    <body style="font-family:sans-serif;text-align:center;padding-top:4em;">
      <h1>Hello from ${var.project_name}</h1>
      <p>instance #${count.index + 1} · served by python3 http.server</p>
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
