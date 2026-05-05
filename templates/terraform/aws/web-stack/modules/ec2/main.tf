data "aws_ami" "amazon_linux" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }
}

resource "aws_instance" "web" {
  ami                    = data.aws_ami.amazon_linux.id
  instance_type          = var.instance_type
  subnet_id              = var.subnet_id
  vpc_security_group_ids = [var.security_group_id]

  user_data = <<-EOF
    #!/bin/bash
    yum install -y httpd
    echo "Hello from ${var.project_name}" > /var/www/html/index.html
    systemctl start httpd
    systemctl enable httpd
  EOF

  tags = merge(var.tags, {
    Name = "${var.project_name}-web"
  })
}

resource "aws_lb_target_group_attachment" "web" {
  target_group_arn = var.target_group_arn
  target_id        = aws_instance.web.id
  port             = 80
}
