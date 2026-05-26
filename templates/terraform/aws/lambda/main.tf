locals {
  common_tags = merge(
    {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "archie"
    },
    var.tags,
  )
}

# CloudWatch Log Group
resource "aws_cloudwatch_log_group" "lambda_logs" {
  name              = "/aws/lambda/${var.project_name}-${var.environment}-function"
  retention_in_days = var.log_retention_days
  tags              = local.common_tags
}

# IAM Role for Lambda
resource "aws_iam_role" "lambda_role" {
  name = "${var.project_name}-${var.environment}-lambda-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
  tags = local.common_tags
}

# Basic Lambda execution policy
resource "aws_iam_role_policy_attachment" "lambda_basic_policy" {
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
  role       = aws_iam_role.lambda_role.name
}

# X-Ray policy (conditional)
resource "aws_iam_role_policy_attachment" "lambda_xray_policy" {
  count      = var.enable_xray ? 1 : 0
  policy_arn = "arn:aws:iam::aws:policy/AWSXRayDaemonWriteAccess"
  role       = aws_iam_role.lambda_role.name
}

# SQS Dead Letter Queue (conditional)
resource "aws_sqs_queue" "dlq" {
  count = var.enable_dlq ? 1 : 0
  name  = "${var.project_name}-${var.environment}-dlq"
  tags  = local.common_tags
}

# DLQ policy for Lambda (conditional)
resource "aws_iam_role_policy" "lambda_dlq_policy" {
  count = var.enable_dlq ? 1 : 0
  name  = "${var.project_name}-${var.environment}-lambda-dlq-policy"
  role  = aws_iam_role.lambda_role.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "sqs:SendMessage",
          "sqs:GetQueueAttributes"
        ]
        Resource = aws_sqs_queue.dlq[0].arn
      }
    ]
  })
}

# Lambda function code archive
data "archive_file" "handler_zip" {
  type        = "zip"
  output_path = "${path.module}/handler.zip"
  source {
    filename = "lambda_function.py"
    content  = <<-EOF
      import json
      import os
      import random

      def lambda_handler(event, context):
          messages = [
              "Governance in the deploy path, not around it",
              "5 fields instead of 50",
              "Drift detected. One click to fix.",
              "The developer deploys. The PE defines the rules.",
              "Your Terraform stays. We govern on top.",
              "Deploy blocked: unresolved drift. Remediate first.",
              "9 resources. 10 config fields. One click.",
              "The real complexity starts the day after deploy.",
              "Detection is solved. The gap is between detected and fixed.",
              "Describe. Generate. Govern. Deploy."
          ]

          page_title = os.environ.get("PAGE_TITLE", "AskArchie")
          button_color = os.environ.get("BUTTON_COLOR", "#3B82F6")
          random_message = random.choice(messages)

          html_content = f"""<!DOCTYPE html>
      <html lang="en">
      <head>
          <meta charset="utf-8">
          <meta name="viewport" content="width=device-width, initial-scale=1">
          <title>{page_title}</title>
          <style>
              body {{
                  margin: 0;
                  padding: 0;
                  background-color: #0B0E14;
                  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                  display: flex;
                  flex-direction: column;
                  justify-content: center;
                  align-items: center;
                  min-height: 100vh;
                  text-align: center;
              }}
              .message {{
                  color: #F1F5F9;
                  font-weight: bold;
                  font-size: 42px;
                  margin-bottom: 20px;
                  max-width: 80%;
                  line-height: 1.2;
              }}
              .subtitle {{
                  color: #64748B;
                  font-size: 18px;
                  margin-bottom: 40px;
              }}
              .button {{
                  background-color: {button_color};
                  color: white;
                  border: none;
                  padding: 12px 24px;
                  font-size: 18px;
                  border-radius: 8px;
                  cursor: pointer;
                  margin-bottom: 20px;
              }}
              .button:hover {{
                  opacity: 0.9;
              }}
              .footer {{
                  color: #64748B;
                  font-size: 14px;
              }}
          </style>
      </head>
      <body>
          <div class="message">{random_message}</div>
          <div class="subtitle">{page_title}</div>
          <button class="button" onclick="window.location.reload()">Show me another</button>
          <div class="footer">askarchie.io</div>
      </body>
      </html>"""

          return {
              "statusCode": 200,
              "headers": {
                  "Content-Type": "text/html; charset=utf-8",
                  "Cache-Control": "no-cache, no-store, must-revalidate",
                  "Pragma": "no-cache",
                  "Expires": "0"
              },
              "body": html_content
          }
    EOF
  }
}

# Lambda Function
resource "aws_lambda_function" "main" {
  filename         = data.archive_file.handler_zip.output_path
  function_name    = "${var.project_name}-${var.environment}-function"
  role             = aws_iam_role.lambda_role.arn
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.12"
  memory_size      = var.lambda_memory
  timeout          = var.lambda_timeout
  source_code_hash = data.archive_file.handler_zip.output_base64sha256

  reserved_concurrent_executions = var.reserved_concurrency > 0 ? var.reserved_concurrency : null

  environment {
    variables = {
      PAGE_TITLE   = var.page_title
      BUTTON_COLOR = var.button_color
    }
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
  depends_on = [aws_cloudwatch_log_group.lambda_logs]
}

# Lambda Function URL
resource "aws_lambda_function_url" "main" {
  function_name      = aws_lambda_function.main.function_name
  authorization_type = "NONE"

  cors {
    allow_credentials = false
    allow_origins     = ["*"]
    allow_methods     = ["GET"]
    allow_headers     = ["date", "keep-alive"]
    expose_headers    = ["date", "keep-alive"]
    max_age           = 86400
  }
}

# Lambda permissions for Function URL (both required — see README)
resource "aws_lambda_permission" "function_url" {
  statement_id           = "FunctionURLAllowPublicAccess"
  action                 = "lambda:InvokeFunctionUrl"
  function_name          = aws_lambda_function.main.function_name
  principal              = "*"
  function_url_auth_type = "NONE"
}

resource "aws_lambda_permission" "function_invoke" {
  statement_id  = "AllowFunctionUrlInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.main.function_name
  principal     = "*"
}
