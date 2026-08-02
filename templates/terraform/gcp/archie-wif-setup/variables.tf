variable "project_id" {
  description = "Your GCP project id — where Archie will deploy. (operator supplies)"
  type        = string
}

# ── Archie's trust anchor — do NOT change unless Archie told you to ──────────
variable "archie_aws_account" {
  description = "Archie's AWS worker account id (the identity your project trusts)."
  type        = string
  default     = "416851285955"
}

variable "archie_worker_role" {
  description = "Archie's AWS worker role name (the only identity allowed to impersonate the deployer SA)."
  type        = string
  default     = "v3-archie-worker-lambda-role-prod-use1"
}

# ── Names + scope (sensible defaults; a PE can lock/override) ────────────────
variable "pool_id" {
  description = "Workload identity pool id."
  type        = string
  default     = "archie-pool"
}

variable "provider_id" {
  description = "AWS provider id within the pool."
  type        = string
  default     = "archie-aws"
}

variable "deployer_sa_id" {
  description = "Deployer service-account id (the SA Archie impersonates)."
  type        = string
  default     = "archie-deployer"
}

variable "deployer_role" {
  description = "Role granted to the deployer SA. Editor to start; scope down to least-privilege for production."
  type        = string
  default     = "roles/editor"
}
