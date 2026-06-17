# Outputs echo the EFFECTIVE (governed) config so the stack drawer shows
# non-prod vs prod differences at a glance — the visible proof of governance.

output "function_url" {
  description = "HTTP URL of the deployed Lambda."
  value       = module.lambda.function_url
}

output "function_name" {
  description = "Name of the Lambda function."
  value       = module.lambda.function_name
}

output "memory_size_mb" {
  description = "Effective Lambda memory (MB) — governed."
  value       = module.lambda.memory_size_mb
}

output "timeout_seconds" {
  description = "Effective Lambda timeout (s) — governed."
  value       = module.lambda.timeout_seconds
}

output "log_retention_days" {
  description = "Effective log retention (days) — governed."
  value       = module.lambda.log_retention_days
}

output "reserved_concurrency" {
  description = "Effective reserved concurrency — governed."
  value       = module.lambda.reserved_concurrency
}

output "tracing_enabled" {
  description = "Whether X-Ray tracing is on — governed."
  value       = module.lambda.tracing_enabled
}

output "dlq_enabled" {
  description = "Whether a dead-letter queue is provisioned — governed."
  value       = module.lambda.dlq_enabled
}
