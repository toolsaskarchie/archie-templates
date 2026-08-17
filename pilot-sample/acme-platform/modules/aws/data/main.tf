resource "aws_db_subnet_group" "main" {
  name       = "${var.project}-${var.environment}-db"
  subnet_ids = var.subnet_ids
  tags       = var.tags
}

resource "aws_security_group" "db" {
  name        = "${var.project}-${var.environment}-db"
  description = "Postgres access for ${var.project}"
  vpc_id      = var.vpc_id
  tags        = var.tags
}

resource "aws_vpc_security_group_ingress_rule" "db" {
  count                        = length(var.allowed_security_group_ids)
  security_group_id            = aws_security_group.db.id
  referenced_security_group_id = var.allowed_security_group_ids[count.index]
  from_port                    = 5432
  to_port                      = 5432
  ip_protocol                  = "tcp"
}

resource "aws_db_instance" "main" {
  identifier = "${var.project}-${var.environment}-pg"
  engine     = "postgres"
  # THE MODULE COULD NOT DEPLOY WITHOUT THESE. `aws_db_instance` requires a
  # master username, and neither it nor a password was ever set — so every
  # apply reached "Error: \"username\": required field is not set" AFTER
  # creating the subnet group and security group, and rolled back. A plan does
  # not catch it either: the field is required by the provider at apply.
  #
  # The password is deliberately NOT a variable. `manage_master_user_password`
  # hands generation and rotation to AWS and stores it in Secrets Manager under
  # the CMK this module already takes, so no secret is typed by a human, passed
  # through Archie, or written into terraform state.
  username                            = var.master_username
  manage_master_user_password         = true
  master_user_secret_kms_key_id       = var.kms_key_arn
  engine_version                      = "16.3"
  instance_class                      = var.instance_class
  allocated_storage                   = var.allocated_storage
  storage_type                        = "gp3"
  storage_encrypted                   = true
  kms_key_id                          = var.kms_key_arn
  db_subnet_group_name                = aws_db_subnet_group.main.name
  vpc_security_group_ids              = [aws_security_group.db.id]
  multi_az                            = var.multi_az
  backup_retention_period             = var.backup_retention_days
  deletion_protection                 = var.deletion_protection
  performance_insights_enabled        = true
  performance_insights_kms_key_id     = var.kms_key_arn
  iam_database_authentication_enabled = true
  publicly_accessible                 = false
  copy_tags_to_snapshot               = true
  auto_minor_version_upgrade          = true
  tags                                = var.tags
}
