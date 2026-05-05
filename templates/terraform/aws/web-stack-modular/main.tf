locals {
  common_tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "archie"
  }
}

module "vpc" {
  source = "./modules/vpc"

  project_name = var.project_name
  environment  = var.environment
  vpc_cidr     = var.vpc_cidr
  tags         = local.common_tags
}

module "alb" {
  source = "./modules/alb"

  project_name  = var.project_name
  vpc_id        = module.vpc.vpc_id
  subnet_ids    = module.vpc.public_subnet_ids
  allowed_cidrs = var.allowed_cidrs
  tags          = local.common_tags
}

module "ec2" {
  source = "./modules/ec2"

  project_name      = var.project_name
  instance_type     = var.instance_type
  subnet_id         = module.vpc.public_subnet_ids[0]
  security_group_id = module.alb.web_security_group_id
  target_group_arn  = module.alb.target_group_arn
  tags              = local.common_tags
}
