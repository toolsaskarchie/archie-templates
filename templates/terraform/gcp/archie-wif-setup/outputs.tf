# The three NON-SECRET values you paste into Archie (Settings -> Cloud Accounts
# -> GCP). None of these is a credential — there is no key to copy.

output "project_id" {
  description = "GCP project id."
  value       = var.project_id
}

output "deployer_sa_email" {
  description = "The SA Archie impersonates (keyless)."
  value       = google_service_account.deployer.email
}

output "wif_audience" {
  description = "The workload-identity provider audience Archie federates against."
  value       = "//iam.googleapis.com/projects/${data.google_project.this.number}/locations/global/workloadIdentityPools/${google_iam_workload_identity_pool.archie.workload_identity_pool_id}/providers/${google_iam_workload_identity_pool_provider.aws.workload_identity_pool_provider_id}"
}
