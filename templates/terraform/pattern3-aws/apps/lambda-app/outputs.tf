output "function_name" {
  description = "Name of the Lambda function."
  value       = module.lambda.function_name
}

output "function_arn" {
  description = "ARN of the Lambda function."
  value       = module.lambda.function_arn
}

output "function_url" {
  description = "Public Function URL (if exposed)."
  value       = try(module.lambda.function_url, "")
}
