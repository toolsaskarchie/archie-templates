output "fqdn" {
  description = "Postgres FQDN."
  value       = azurerm_postgresql_flexible_server.main.fqdn
}
