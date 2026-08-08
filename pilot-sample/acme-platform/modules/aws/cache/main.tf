resource "aws_elasticache_subnet_group" "main" {
  name       = "${var.project}-${var.environment}-cache"
  subnet_ids = var.subnet_ids
  tags       = var.tags
}

resource "aws_security_group" "cache" {
  name        = "${var.project}-${var.environment}-cache"
  description = "Redis access for ${var.project}"
  vpc_id      = var.vpc_id
  tags        = var.tags
}

resource "aws_vpc_security_group_ingress_rule" "cache" {
  count                        = length(var.allowed_security_group_ids)
  security_group_id            = aws_security_group.cache.id
  referenced_security_group_id = var.allowed_security_group_ids[count.index]
  from_port                    = 6379
  to_port                      = 6379
  ip_protocol                  = "tcp"
}

resource "aws_elasticache_replication_group" "main" {
  replication_group_id       = "${var.project}-${var.environment}-redis"
  description                = "${var.project} ${var.environment} cache"
  engine                     = "redis"
  engine_version             = "7.1"
  node_type                  = var.node_type
  num_cache_clusters         = var.replica_count + 1
  parameter_group_name       = "default.redis7"
  subnet_group_name          = aws_elasticache_subnet_group.main.name
  security_group_ids         = [aws_security_group.cache.id]
  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  kms_key_id                 = var.kms_key_arn
  multi_az_enabled           = var.multi_az_enabled
  automatic_failover_enabled = var.multi_az_enabled
  snapshot_retention_limit   = var.snapshot_retention_limit
  apply_immediately          = false
  tags                       = var.tags
}
