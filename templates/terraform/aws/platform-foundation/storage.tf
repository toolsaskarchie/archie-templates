# -----------------------------------------------------------------------------
# Storage — encrypted, versioned, private assets bucket + config table.
# -----------------------------------------------------------------------------

resource "aws_s3_bucket" "assets" {
  bucket = local.bucket_name
}

resource "aws_s3_bucket_public_access_block" "assets" {
  bucket                  = aws_s3_bucket.assets.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "assets" {
  bucket = aws_s3_bucket.assets.id
  versioning_configuration {
    status = var.s3_versioning_enabled ? "Enabled" : "Suspended"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "assets" {
  bucket = aws_s3_bucket.assets.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "assets" {
  bucket     = aws_s3_bucket.assets.id
  depends_on = [aws_s3_bucket_versioning.assets]

  rule {
    id     = "expire-noncurrent"
    status = "Enabled"
    filter {}
    noncurrent_version_expiration {
      noncurrent_days = var.s3_noncurrent_expiration_days
    }
  }
}

resource "aws_dynamodb_table" "config" {
  name         = "${local.name}-config"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "key"

  attribute {
    name = "key"
    type = "S"
  }

  point_in_time_recovery {
    enabled = var.dynamodb_point_in_time_recovery
  }

  server_side_encryption {
    enabled = true
  }

  tags = { Name = "${local.name}-config" }
}
