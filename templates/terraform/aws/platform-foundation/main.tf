# -----------------------------------------------------------------------------
# Shared data + naming
# -----------------------------------------------------------------------------

data "aws_caller_identity" "current" {}

locals {
  name        = "${var.project_name}-${var.environment}"
  bucket_name = "${var.project_name}-${var.environment}-assets-${data.aws_caller_identity.current.account_id}-${var.region}"
  azs         = ["${var.region}a", "${var.region}b"]
}
