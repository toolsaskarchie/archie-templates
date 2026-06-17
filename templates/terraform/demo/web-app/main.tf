# Demo app — Web stack (ALB + EC2 + VPC + security groups), governed by Archie.
# Thin root: consumes the reusable web-modular module pinned to an IMMUTABLE
# commit so a live demo is deterministic. Swap ?ref=<sha> -> ?ref=v1.0.0 once tagged.
# No backend/provider block on purpose — Archie's native-TF engine injects the
# S3 backend, provider, and tenant credentials at deploy time.

module "web" {
  source = "git::https://github.com/toolsaskarchie/archie-templates.git//templates/terraform/pattern3-aws/modules/web-modular?ref=4903fd3c8825d505001cb47e35a26385e418e7a8"

  project_name       = var.project_name
  environment        = var.environment
  vpc_cidr           = var.vpc_cidr
  instance_type      = var.instance_type
  ec2_instance_count = var.ec2_instance_count

  # ── The governance star: who can reach the ALB. Lock this per profile. ──
  allowed_cidrs = var.allowed_cidrs

  target_port     = var.target_port
  internal        = var.internal
  enable_https    = var.enable_https
  certificate_arn = var.certificate_arn
}
