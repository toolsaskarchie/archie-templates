module "vpc" {
  source = "git::https://github.com/toolsaskarchie/archie-templates.git//templates/terraform/pattern3-aws/modules/vpc?ref=main"

  project_name = var.project_name
  environment  = var.environment
  vpc_cidr     = var.vpc_cidr
  subnet_count = var.subnet_count
  tags         = var.tags
}
