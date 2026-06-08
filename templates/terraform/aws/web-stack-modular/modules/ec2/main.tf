data "aws_ami" "amazon_linux" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }
}

# Backend instance(s) — one per element of subnet_ids, round-robin if count > len(subnet_ids).
# user_data uses python3 (pre-installed on AL2023) so no internet egress required at boot —
# works in restricted-egress accounts (CloudGuru labs, isolated VPCs without NAT, etc.).

resource "aws_instance" "web" {
  count                  = var.instance_count
  ami                    = data.aws_ami.amazon_linux.id
  instance_type          = var.instance_type
  subnet_id              = var.subnet_ids[count.index % length(var.subnet_ids)]
  vpc_security_group_ids = [var.backend_security_group_id]

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

  tags = merge(var.tags, {
    Name = "${var.project_name}-web-${count.index + 1}"
  })
}

resource "aws_lb_target_group_attachment" "web" {
  count            = var.instance_count
  target_group_arn = var.target_group_arn
  target_id        = aws_instance.web[count.index].id
  port             = var.target_port
}
