output "function_url" {
  description = "The HTTP URL endpoint for the Lambda function."
  value       = aws_lambda_function_url.main.function_url
}

output "function_name" {
  description = "Name of the Lambda function."
  value       = aws_lambda_function.main.function_name
}

output "log_group_name" {
  description = "Name of the CloudWatch log group."
  value       = aws_cloudwatch_log_group.lambda_logs.name
}

output "dlq_url" {
  description = "URL of the dead letter queue (null when disabled)."
  value       = var.enable_dlq ? aws_sqs_queue.dlq[0].url : null
}
