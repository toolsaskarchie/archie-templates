# Demo app — Lambda, governed by Archie.
# Thin root: consumes the reusable lambda module pinned to an IMMUTABLE commit
# so a live demo is deterministic. Swap ?ref=<sha> -> ?ref=v1.0.0 once tagged.
# No backend/provider block on purpose — Archie's native-TF engine injects the
# S3 backend, provider, and tenant credentials at deploy time.

module "lambda" {
  source = "git::https://github.com/toolsaskarchie/archie-templates.git//templates/terraform/pattern3-aws/modules/lambda?ref=4903fd3c8825d505001cb47e35a26385e418e7a8"

  project_name = var.project_name
  environment  = var.environment

  # ── Governable levers (lock these per profile in Archie's Govern step) ──
  lambda_memory        = var.lambda_memory
  lambda_timeout       = var.lambda_timeout
  log_retention_days   = var.log_retention_days
  reserved_concurrency = var.reserved_concurrency
  enable_xray          = var.enable_xray
  enable_dlq           = var.enable_dlq

  tags = var.tags
}
