# Non-prod profile — relaxed, cheap. These are the values a PE would set as the
# non-prod governance defaults (and may leave unlocked for devs to tweak).
project_name         = "archie-demo-lambda"
environment          = "nonprod"
lambda_memory        = 256
lambda_timeout       = 15
log_retention_days   = 7
reserved_concurrency = 0
enable_xray          = false
enable_dlq           = false
