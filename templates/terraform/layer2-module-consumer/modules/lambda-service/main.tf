locals {
  fn_name   = "${var.project_name}-${var.environment}-${var.function_name_suffix}"
  role_name = var.role_name_override != "" ? var.role_name_override : "${local.fn_name}-role"
  log_group = "/aws/lambda/${local.fn_name}"

  common_tags = merge(
    {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "Archie"
      Module      = "lambda-service"
    },
    var.tags,
    var.additional_tags,
  )
}

# Bundle the handler at apply time so consumers don't need to ship a zip.
data "archive_file" "handler_zip" {
  type        = "zip"
  output_path = "${path.module}/handler.zip"
  source {
    filename = "lambda_function.py"
    content  = <<-EOF
      import json
      import os


      def lambda_handler(event, context):
          payload = {
              "message": "Hello from lambda-service module",
              "project": os.environ.get("PROJECT_NAME", "unknown"),
              "environment": os.environ.get("ENVIRONMENT", "unknown"),
          }
          return {
              "statusCode": 200,
              "headers": {"Content-Type": "application/json"},
              "body": json.dumps(payload),
          }
    EOF
  }
}

resource "aws_cloudwatch_log_group" "this" {
  name              = local.log_group
  retention_in_days = var.log_retention_days
  kms_key_id        = var.kms_key_arn != "" ? var.kms_key_arn : null
  tags              = local.common_tags
}

resource "aws_iam_role" "this" {
  name = local.role_name
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Action    = "sts:AssumeRole"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
  tags = local.common_tags
}

# Inline policy bundles the basics + conditional DLQ / X-Ray grants so we
# never need conditional aws_iam_role_policy_attachment counts.
resource "aws_iam_role_policy" "this" {
  name = "${local.role_name}-inline"
  role = aws_iam_role.this.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat(
      [
        {
          Effect = "Allow"
          Action = [
            "logs:CreateLogStream",
            "logs:PutLogEvents",
          ]
          Resource = "${aws_cloudwatch_log_group.this.arn}:*"
        },
      ],
      var.enable_dlq ? [{
        Effect = "Allow"
        Action = ["sqs:SendMessage", "sqs:GetQueueAttributes"]
        Resource = aws_sqs_queue.dlq[0].arn
      }] : [],
      var.enable_xray ? [{
        Effect   = "Allow"
        Action   = ["xray:PutTraceSegments", "xray:PutTelemetryRecords"]
        Resource = "*"
      }] : [],
    )
  })
}

resource "aws_sqs_queue" "dlq" {
  count = var.enable_dlq ? 1 : 0
  name  = "${local.fn_name}-dlq"
  tags  = local.common_tags
}

resource "aws_lambda_function" "this" {
  function_name    = local.fn_name
  role             = aws_iam_role.this.arn
  handler          = var.handler
  runtime          = var.runtime
  memory_size      = var.memory_size
  timeout          = var.timeout
  filename         = data.archive_file.handler_zip.output_path
  source_code_hash = data.archive_file.handler_zip.output_base64sha256

  reserved_concurrent_executions = var.reserved_concurrency > 0 ? var.reserved_concurrency : null
  kms_key_arn                    = var.kms_key_arn != "" ? var.kms_key_arn : null

  environment {
    variables = merge(
      {
        PROJECT_NAME = var.project_name
        ENVIRONMENT  = var.environment
      },
      var.environment_variables,
    )
  }

  # Pin Lambda at our log group so retention applies + destroy doesn't leak
  # an auto-created group on first invocation.
  logging_config {
    log_format = "Text"
    log_group  = aws_cloudwatch_log_group.this.name
  }

  dynamic "dead_letter_config" {
    for_each = var.enable_dlq ? [1] : []
    content {
      target_arn = aws_sqs_queue.dlq[0].arn
    }
  }

  dynamic "tracing_config" {
    for_each = var.enable_xray ? [1] : []
    content {
      mode = "Active"
    }
  }

  tags       = local.common_tags
  depends_on = [aws_cloudwatch_log_group.this]
}

# Stable "live" pointer so consumers can wire alarms / event sources at an
# alias instead of $LATEST. Standard module hygiene.
resource "aws_lambda_alias" "live" {
  name             = "live"
  function_name    = aws_lambda_function.this.function_name
  function_version = "$LATEST"
}

# Retry behavior — conservative defaults, overridable per consumer.
resource "aws_lambda_function_event_invoke_config" "this" {
  function_name                = aws_lambda_function.this.function_name
  maximum_event_age_in_seconds = 3600
  maximum_retry_attempts       = 2
}

resource "aws_cloudwatch_metric_alarm" "errors" {
  count               = var.enable_alarms ? 1 : 0
  alarm_name          = "${local.fn_name}-errors"
  alarm_description   = "Errors on ${local.fn_name} exceeded ${var.alarm_threshold}."
  namespace           = "AWS/Lambda"
  metric_name         = "Errors"
  statistic           = "Sum"
  period              = 60
  evaluation_periods  = 1
  threshold           = var.alarm_threshold
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = aws_lambda_function.this.function_name
  }

  alarm_actions = var.alarm_sns_topic_arn != "" ? [var.alarm_sns_topic_arn] : []
  tags          = local.common_tags
}
