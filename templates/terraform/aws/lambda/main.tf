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

# DynamoDB table
resource "aws_dynamodb_table" "main" {
  name           = var.table_name
  billing_mode   = "PROVISIONED"
  read_capacity  = var.read_capacity
  write_capacity = var.write_capacity
  hash_key       = var.partition_key

  attribute {
    name = var.partition_key
    type = "S"
  }

  tags = local.common_tags
}

# IAM role for Lambda execution
resource "aws_iam_role" "execution_role" {
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

# Attach basic execution policy
resource "aws_iam_role_policy_attachment" "lambda_basic" {
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
  role       = aws_iam_role.execution_role.name
}

# IAM policy for DynamoDB access
resource "aws_iam_role_policy" "dynamodb_access" {
  name = "${var.project_name}-${var.environment}-dynamodb-policy"
  role = aws_iam_role.execution_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:Query",
          "dynamodb:Scan"
        ]
        Resource = aws_dynamodb_table.main.arn
      }
    ]
  })
}

# CloudWatch log group
resource "aws_cloudwatch_log_group" "lambda_logs" {
  name              = "/aws/lambda/${var.project_name}-${var.environment}-archie-demo"
  retention_in_days = var.log_retention_days

  tags = local.common_tags
}

# Lambda function code archive
data "archive_file" "lambda_zip" {
  type        = "zip"
  output_path = "${path.module}/lambda_function.zip"
  source {
    filename = "lambda_function.py"
    content  = <<-EOF
import json
import os
import random

def lambda_handler(event, context):
    # Get configuration from environment variables
    page_title = os.environ.get('PAGE_TITLE', 'AskArchie — Cloud Standards Platform')
    button_color = os.environ.get('BUTTON_COLOR', '#3B82F6')

    # Random messages
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

    # Select random message
    random_message = random.choice(messages)

    # Generate HTML response
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
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
            font-size: 42px;
            font-weight: bold;
            margin-bottom: 20px;
            max-width: 80%;
            line-height: 1.2;
        }}
        .subtitle {{
            color: #64748B;
            font-size: 18px;
            margin-bottom: 30px;
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
            transition: opacity 0.2s;
        }}
        .button:hover {{
            opacity: 0.8;
        }}
        .footer {{
            color: #64748B;
            font-size: 14px;
        }}
        @media (max-width: 768px) {{
            .message {{
                font-size: 28px;
                max-width: 90%;
            }}
            .subtitle {{
                font-size: 16px;
            }}
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
        'statusCode': 200,
        'headers': {
            'Content-Type': 'text/html; charset=utf-8',
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Pragma': 'no-cache',
            'Expires': '0'
        },
        'body': html_content
    }
EOF
  }
}

# Lambda function
resource "aws_lambda_function" "main" {
  filename         = data.archive_file.lambda_zip.output_path
  function_name    = "${var.project_name}-${var.environment}-archie-demo"
  role             = aws_iam_role.execution_role.arn
  handler          = "lambda_function.lambda_handler"
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  runtime          = "python3.12"
  memory_size      = var.lambda_memory
  timeout          = var.lambda_timeout
  architectures    = ["arm64"]

  environment {
    variables = {
      PAGE_TITLE   = var.page_title
      BUTTON_COLOR = var.button_color
      TABLE_NAME   = aws_dynamodb_table.main.name
    }
  }

  depends_on = [aws_cloudwatch_log_group.lambda_logs]

  tags = local.common_tags
}

# Lambda Function URL
resource "aws_lambda_function_url" "main" {
  function_name      = aws_lambda_function.main.function_name
  authorization_type = var.auth_type

  cors {
    allow_credentials = false
    allow_origins     = ["*"]
    allow_methods     = ["GET", "POST"]
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
  function_url_auth_type = var.auth_type
}

resource "aws_lambda_permission" "function_invoke" {
  statement_id  = "AllowFunctionUrlInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.main.function_name
  principal     = "*"
}
