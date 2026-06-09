data "aws_ami" "amazon_linux" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }
}

# Backend instance(s) - one per element of subnet_ids, round-robin if count > len(subnet_ids).
# user_data uses python3 (pre-installed on AL2023) so no internet egress required at boot -
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

    # IMDSv2 - proof the lab works: read live instance metadata
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
