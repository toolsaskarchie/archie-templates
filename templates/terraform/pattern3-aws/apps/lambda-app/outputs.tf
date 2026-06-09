output "function_name" {
  description = "Name of the Lambda function."
  value       = module.lambda.function_name
}

output "function_url" {
  description = "Public Function URL (if exposed)."
  value       = try(module.lambda.function_url, "")
}

output "log_group_name" {
  description = "CloudWatch log group for the function."
  value       = module.lambda.log_group_name
}
