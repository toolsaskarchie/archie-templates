# -----------------------------------------------------------------------------
# Messaging — encrypted async surfaces.
# -----------------------------------------------------------------------------

resource "aws_sqs_queue" "events" {
  name                      = "${local.name}-events"
  message_retention_seconds = var.sqs_message_retention_seconds
  sqs_managed_sse_enabled   = true
}

resource "aws_sns_topic" "notifications" {
  name              = "${local.name}-notifications"
  kms_master_key_id = "alias/aws/sns"
}
