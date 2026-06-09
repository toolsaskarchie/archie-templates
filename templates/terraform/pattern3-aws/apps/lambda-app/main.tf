module "lambda" {
  source = "git::https://github.com/toolsaskarchie/archie-templates.git//templates/terraform/pattern3-aws/modules/lambda?ref=main"

  project_name   = var.project_name
  environment    = var.environment
  lambda_memory  = var.lambda_memory
  lambda_timeout = var.lambda_timeout
  tags           = var.tags
}
