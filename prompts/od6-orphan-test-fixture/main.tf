# OD-6 test fixture — 10 resources designed to exercise every code path
# in the orphan-detect + delete pipeline. Apply directly with `tofu apply`
# (or `terraform apply`) using CloudGuru sandbox credentials. Do NOT deploy
# via Archie — Archie's OD-0 transformation would stamp these as managed.
#
# Run:
#   AWS_PROFILE=cloudguru tofu init
#   AWS_PROFILE=cloudguru tofu apply -auto-approve
#
# Cleanup after testing (anything OD-6 deleted via Archie will already be
# gone; tofu destroy will skip those via "already destroyed"):
#   AWS_PROFILE=cloudguru tofu destroy -auto-approve

terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "us-east-1"
}

locals {
  suffix = "od6test"
}

############################################################
# Pass 1 — DDB / Lambda / SNS / SQS
############################################################

# 1. DynamoDB table, no protection — happy path delete
resource "aws_dynamodb_table" "simple_table" {
  name         = "od6-simple-${local.suffix}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "id"
  attribute {
    name = "id"
    type = "S"
  }
}

# 2. DynamoDB table WITH deletion protection — hard_blocker test
resource "aws_dynamodb_table" "protected_table" {
  name                        = "od6-protected-${local.suffix}"
  billing_mode                = "PAY_PER_REQUEST"
  hash_key                    = "id"
  deletion_protection_enabled = true
  attribute {
    name = "id"
    type = "S"
  }
}

# 3. Lambda function with no event sources — clean delete
resource "aws_iam_role" "lambda_role" {
  name = "od6-lambda-role-${local.suffix}"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_lambda_function" "simple_lambda" {
  function_name = "od6-simple-lambda-${local.suffix}"
  role          = aws_iam_role.lambda_role.arn
  runtime       = "python3.12"
  handler       = "index.handler"
  filename      = data.archive_file.lambda_zip.output_path
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
}

data "archive_file" "lambda_zip" {
  type        = "zip"
  output_path = "${path.module}/lambda.zip"
  source {
    content  = "def handler(event, context):\n    return 'orphan'\n"
    filename = "index.py"
  }
}

# 4. SNS topic with one subscription (warning test)
resource "aws_sns_topic" "test_topic" {
  name = "od6-topic-${local.suffix}"
}

resource "aws_sns_topic_subscription" "test_sub" {
  topic_arn = aws_sns_topic.test_topic.arn
  protocol  = "email"
  endpoint  = "orphan-test@example.invalid"  # never confirmed, that's fine
}

# 5. SQS queue (no messages — clean delete)
resource "aws_sqs_queue" "test_queue" {
  name = "od6-queue-${local.suffix}"
}

############################################################
# Pass 2 — S3 + EC2
############################################################

# 6. Empty S3 bucket — happy path, no force_empty needed
resource "aws_s3_bucket" "empty_bucket" {
  bucket        = "od6-empty-${local.suffix}-${data.aws_caller_identity.current.account_id}"
  force_destroy = false  # tests Archie's path, not tofu's
}

data "aws_caller_identity" "current" {}

# 7. Non-empty versioned S3 bucket — force_empty checkbox test
resource "aws_s3_bucket" "versioned_bucket" {
  bucket        = "od6-versioned-${local.suffix}-${data.aws_caller_identity.current.account_id}"
  force_destroy = false  # cleanup falls to Archie OD-6 with force_empty
}

resource "aws_s3_bucket_versioning" "versioned_bucket" {
  bucket = aws_s3_bucket.versioned_bucket.id
  versioning_configuration {
    status = "Enabled"
  }
}

# Drop 3 objects + overwrite one to create versions + a delete marker
resource "aws_s3_object" "v1" {
  bucket  = aws_s3_bucket.versioned_bucket.id
  key     = "test-object-1.txt"
  content = "version one"
  depends_on = [aws_s3_bucket_versioning.versioned_bucket]
}

resource "aws_s3_object" "v2" {
  bucket  = aws_s3_bucket.versioned_bucket.id
  key     = "test-object-2.txt"
  content = "version two"
  depends_on = [aws_s3_bucket_versioning.versioned_bucket]
}

resource "aws_s3_object" "v3" {
  bucket  = aws_s3_bucket.versioned_bucket.id
  key     = "test-object-3.txt"
  content = "version three"
  depends_on = [aws_s3_bucket_versioning.versioned_bucket]
}

# NOTE: We are intentionally NOT creating an Object Lock COMPLIANCE bucket
# because once set, the bucket cannot be deleted until the retention period
# expires — would leave permanent crud in CloudGuru. Manual test path: enable
# Object Lock on the empty bucket via console after testing the happy path,
# then re-scan and verify the hard_blocker appears.

# 8. EC2 instance, no termination protection — clean terminate
resource "aws_vpc" "test_vpc" {
  cidr_block           = "10.99.0.0/16"
  enable_dns_hostnames = true
}

resource "aws_subnet" "test_subnet" {
  vpc_id            = aws_vpc.test_vpc.id
  cidr_block        = "10.99.1.0/24"
  availability_zone = "us-east-1a"
}

# Cheapest possible — t3.nano, default Amazon Linux 2023 AMI
data "aws_ssm_parameter" "al2023_ami" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
}

resource "aws_instance" "simple_instance" {
  ami           = data.aws_ssm_parameter.al2023_ami.value
  instance_type = "t3.nano"
  subnet_id     = aws_subnet.test_subnet.id
}

# 9. EC2 instance WITH termination protection — hard_blocker test
resource "aws_instance" "protected_instance" {
  ami                     = data.aws_ssm_parameter.al2023_ami.value
  instance_type           = "t3.nano"
  subnet_id               = aws_subnet.test_subnet.id
  disable_api_termination = true
}

# 10. EC2 with a persistent (non-DeleteOnTermination) attached volume —
# warning test ("EBS volume will persist as orphan")
resource "aws_instance" "instance_with_extra_volume" {
  ami           = data.aws_ssm_parameter.al2023_ami.value
  instance_type = "t3.nano"
  subnet_id     = aws_subnet.test_subnet.id

  ebs_block_device {
    device_name           = "/dev/sdf"
    volume_size           = 1
    delete_on_termination = false  # this is the test case — orphan EBS
  }
}

############################################################
# Outputs — easy copy-paste for ARN-based AWS console verification
############################################################

output "test_resource_names" {
  value = {
    ddb_simple                = aws_dynamodb_table.simple_table.name
    ddb_protected             = aws_dynamodb_table.protected_table.name
    lambda_simple             = aws_lambda_function.simple_lambda.function_name
    sns_with_sub              = aws_sns_topic.test_topic.arn
    sqs_simple                = aws_sqs_queue.test_queue.url
    s3_empty                  = aws_s3_bucket.empty_bucket.id
    s3_versioned_nonempty     = aws_s3_bucket.versioned_bucket.id
    ec2_simple                = aws_instance.simple_instance.id
    ec2_protected             = aws_instance.protected_instance.id
    ec2_with_persistent_vol   = aws_instance.instance_with_extra_volume.id
  }
}

output "expected_orphan_count" {
  value       = 10
  description = "Number of resources Archie should classify as 'unmanaged' orphan after scan (plus the VPC/subnet/IAM role which are technically orphans too — 13 total approx)"
}
