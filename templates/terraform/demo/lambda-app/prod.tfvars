# Production profile — hardened. In Archie's Govern step these become LOCKED
# fields on the production profile: a dev deploying to prod cannot lower them.
project_name         = "archie-demo-lambda"
environment          = "prod"
lambda_memory        = 1024 # LOCKED — prod floor
lambda_timeout       = 30   # LOCKED
log_retention_days   = 90   # LOCKED — compliance retention
reserved_concurrency = 50   # LOCKED — guarantee capacity
enable_xray          = true # LOCKED — tracing on in prod
enable_dlq           = true # LOCKED — no silent failures in prod
