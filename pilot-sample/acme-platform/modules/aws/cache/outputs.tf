output "primary_endpoint" {
  description = "Redis primary endpoint."
  value       = aws_elasticache_replication_group.main.primary_endpoint_address
}
output "security_group_id" {
  description = "Cache security group."
  value       = aws_security_group.cache.id
}
