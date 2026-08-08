data "aws_region" "current" {}

locals {
  # The Archie demo page — same asset the Kubernetes workload serves, so every
  # web-facing entrypoint in this platform lands on one branded page instead of
  # a stock nginx splash. Base64'd into the container command because ECS has no
  # ConfigMap equivalent and shell-quoting HTML in a task definition is a trap.
  demo_page = templatefile("${path.module}/../../shared/demo-page.html.tftpl", {
    page_title   = "${var.project} · ${var.environment}"
    button_color = "#3B82F6"
    message      = "Describe. Generate. Govern. Deploy."
    cloud        = "AWS"
    environment  = var.environment
    served_by    = "ALB → ECS Fargate"
  })
}

resource "aws_security_group" "alb" {
  name        = "${var.project}-${var.environment}-alb"
  description = "Public ingress for ${var.project}"
  vpc_id      = var.vpc_id
  tags        = var.tags
}

resource "aws_vpc_security_group_ingress_rule" "alb_https" {
  count             = length(var.ingress_cidrs)
  security_group_id = aws_security_group.alb.id
  cidr_ipv4         = var.ingress_cidrs[count.index]
  from_port         = 443
  to_port           = 443
  ip_protocol       = "tcp"
}

resource "aws_security_group" "service" {
  name        = "${var.project}-${var.environment}-svc"
  description = "Task security group for ${var.project}"
  vpc_id      = var.vpc_id
  tags        = var.tags
}

resource "aws_lb" "main" {
  name                       = "${var.project}-${var.environment}-alb"
  internal                   = false
  load_balancer_type         = "application"
  security_groups            = [aws_security_group.alb.id]
  subnets                    = var.public_subnet_ids
  drop_invalid_header_fields = true
  enable_deletion_protection = var.environment == "prod"
  tags                       = var.tags
}

resource "aws_lb_target_group" "main" {
  name        = "${var.project}-${var.environment}-tg"
  port        = 8080
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = var.vpc_id
  health_check {
    path    = "/healthz"
    matcher = "200"
  }
  tags = var.tags
}

resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.main.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = var.certificate_arn
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.main.arn
  }
  tags = var.tags
}

resource "aws_cloudwatch_log_group" "service" {
  name              = "/acme/${var.project}/${var.environment}"
  retention_in_days = var.log_retention_days
  kms_key_id        = var.kms_key_arn
  tags              = var.tags
}

resource "aws_ecs_cluster" "main" {
  name = "${var.project}-${var.environment}"
  setting {
    name  = "containerInsights"
    value = "enabled"
  }
  tags = var.tags
}

resource "aws_ecs_service" "main" {
  name            = "${var.project}-${var.environment}-svc"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.main.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"
  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [aws_security_group.service.id]
    assign_public_ip = false
  }
  load_balancer {
    target_group_arn = aws_lb_target_group.main.arn
    container_name   = var.project
    container_port   = 8080
  }
  tags = var.tags
}

resource "aws_ecs_task_definition" "main" {
  family                   = "${var.project}-${var.environment}"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 512
  memory                   = 1024
  execution_role_arn       = aws_iam_role.execution.arn
  container_definitions = jsonencode([{
    name       = var.project
    image      = "public.ecr.aws/nginx/nginx:stable"
    entryPoint = ["/bin/sh", "-c"]
    command = [join(" && ", [
      "echo ${base64encode(local.demo_page)} | base64 -d > /usr/share/nginx/html/index.html",
      "sed -i 's/listen       80;/listen 8080;/' /etc/nginx/conf.d/default.conf",
      "nginx -g 'daemon off;'",
    ])]
    portMappings = [{ containerPort = 8080 }]
    logConfiguration = {
      logDriver = "awslogs"
      options   = { awslogs-group = aws_cloudwatch_log_group.service.name, awslogs-region = data.aws_region.current.name, awslogs-stream-prefix = "ecs" }
    }
  }])
  tags = var.tags
}

resource "aws_iam_role" "execution" {
  name = "${var.project}-${var.environment}-exec"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "ecs-tasks.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
  tags = var.tags
}
