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

# ─── Governance-visible outputs ──────────────────────────────────────────────
# These echo the EFFECTIVE config the Lambda was deployed with. Surfaces
# profile differences in the stack drawer — non-prod vs production show
# different values here when the PE locked different defaults per profile.

output "project_name" {
  description = "Project name (resource prefix). Locked by PE typically."
  value       = var.project_name
}

output "environment" {
  description = "Environment label."
  value       = var.environment
}

output "memory_size_mb" {
  description = "Lambda memory (MB). Profile lever — non-prod 256, prod 512+."
  value       = aws_lambda_function.main.memory_size
}

output "timeout_seconds" {
  description = "Lambda timeout (seconds)."
  value       = aws_lambda_function.main.timeout
}

output "runtime" {
  description = "Lambda runtime."
  value       = aws_lambda_function.main.runtime
}

output "log_retention_days" {
  description = "CloudWatch log retention (days). Profile lever — non-prod 7, prod 90+."
  value       = aws_cloudwatch_log_group.lambda_logs.retention_in_days
}

output "tracing_enabled" {
  description = "Whether X-Ray active tracing is enabled. Profile lever."
  value       = var.enable_xray
}

output "dlq_enabled" {
  description = "Whether dead letter queue is provisioned. Profile lever."
  value       = var.enable_dlq
}

output "reserved_concurrency" {
  description = "Reserved concurrent executions (0 = unreserved). Profile lever."
  value       = var.reserved_concurrency
}

output "dlq_url" {
  description = "URL of the dead letter queue (null when disabled)."
  value       = var.enable_dlq ? aws_sqs_queue.dlq[0].url : null
}
