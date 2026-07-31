# -----------------------------------------------------------------------------
# Outputs
# -----------------------------------------------------------------------------

output "region" {
  description = "AWS region this stack deployed into. Governance pins this to the approved region via the region locked-field; the value echoes what was actually applied."
  value       = var.region
}

output "vpc_id" {
  description = "Platform VPC id."
  value       = aws_vpc.main.id
}

output "assets_bucket" {
  description = "Assets S3 bucket name."
  value       = aws_s3_bucket.assets.bucket
}

output "config_table" {
  description = "Config DynamoDB table name."
  value       = aws_dynamodb_table.config.name
}

output "events_queue_url" {
  description = "SQS events queue URL."
  value       = aws_sqs_queue.events.url
}

output "notifications_topic_arn" {
  description = "SNS notifications topic ARN."
  value       = aws_sns_topic.notifications.arn
}

output "app_role_arn" {
  description = "Least-privilege application IAM role ARN."
  value       = aws_iam_role.app.arn
}
