# -----------------------------------------------------------------------------
# Observability + IAM — CloudWatch log group and a least-privilege application
# role scoped to THIS stack's resources only.
# -----------------------------------------------------------------------------

resource "aws_cloudwatch_log_group" "app" {
  name              = "/platform/${local.name}"
  retention_in_days = var.log_retention_days
}

data "aws_iam_policy_document" "assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com", "lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "app" {
  name               = "${local.name}-app-role"
  assume_role_policy = data.aws_iam_policy_document.assume.json
  tags               = { Name = "${local.name}-app-role" }
}

data "aws_iam_policy_document" "app" {
  statement {
    sid     = "AssetsBucket"
    actions = ["s3:GetObject", "s3:PutObject", "s3:ListBucket"]
    resources = [
      aws_s3_bucket.assets.arn,
      "${aws_s3_bucket.assets.arn}/*",
    ]
  }
  statement {
    sid       = "ConfigTable"
    actions   = ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:Query", "dynamodb:UpdateItem"]
    resources = [aws_dynamodb_table.config.arn]
  }
  statement {
    sid       = "Messaging"
    actions   = ["sqs:SendMessage", "sns:Publish"]
    resources = [aws_sqs_queue.events.arn, aws_sns_topic.notifications.arn]
  }
  statement {
    sid       = "Logs"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.app.arn}:*"]
  }
}

resource "aws_iam_role_policy" "app" {
  name   = "${local.name}-app-policy"
  role   = aws_iam_role.app.id
  policy = data.aws_iam_policy_document.app.json
}
