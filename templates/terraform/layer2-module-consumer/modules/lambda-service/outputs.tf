output "function_name" {
  description = "Name of the Lambda function."
  value       = aws_lambda_function.this.function_name
}

output "function_arn" {
  description = "ARN of the Lambda function."
  value       = aws_lambda_function.this.arn
}

output "function_alias_arn" {
  description = "ARN of the 'live' alias — wire event sources here, not at $LATEST."
  value       = aws_lambda_alias.live.arn
}

output "function_version" {
  description = "Latest published function version."
  value       = aws_lambda_function.this.version
}

output "role_arn" {
  description = "ARN of the execution IAM role."
  value       = aws_iam_role.this.arn
}

output "role_name" {
  description = "Name of the execution IAM role."
  value       = aws_iam_role.this.name
}

output "log_group_name" {
  description = "CloudWatch log group the function writes to."
  value       = aws_cloudwatch_log_group.this.name
}

output "log_group_arn" {
  description = "ARN of the CloudWatch log group."
  value       = aws_cloudwatch_log_group.this.arn
}

output "dlq_arn" {
  description = "ARN of the dead letter queue (null when disabled)."
  value       = var.enable_dlq ? aws_sqs_queue.dlq[0].arn : null
}

output "alarm_arn" {
  description = "ARN of the errors alarm (null when disabled)."
  value       = var.enable_alarms ? aws_cloudwatch_metric_alarm.errors[0].arn : null
}
