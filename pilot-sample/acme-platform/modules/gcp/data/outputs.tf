output "connection_name" {
  description = "Cloud SQL connection name."
  value       = google_sql_database_instance.main.connection_name
}
