module "web" {
  source = "git::https://github.com/toolsaskarchie/archie-templates.git//templates/terraform/pattern3-aws/modules/web-modular?ref=main"

  project_name       = var.project_name
  environment        = var.environment
  vpc_cidr           = var.vpc_cidr
  instance_type      = var.instance_type
  ec2_instance_count = var.ec2_instance_count
  allowed_cidrs      = var.allowed_cidrs
  target_port        = 80
  internal           = false
  enable_https       = false
  certificate_arn    = ""
}
