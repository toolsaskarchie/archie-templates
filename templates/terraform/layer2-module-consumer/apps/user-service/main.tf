module "lambda" {
  source = "git::https://github.com/toolsaskarchie/archie-templates.git//templates/terraform/layer2-module-consumer/modules/lambda-service?ref=main"

  project_name = var.project_name
  environment  = var.environment
  memory_size  = var.lambda_memory
  timeout      = var.lambda_timeout
  tags         = var.tags
}
