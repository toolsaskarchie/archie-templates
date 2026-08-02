# gcp-archie-wif — a ONE-TIME bootstrap that grants Archie *keyless* access to
# this GCP project via Workload Identity Federation. No service-account key is
# ever created, downloaded, or stored.
#
# The GCP mirror of the AWS `archie_role` bootstrap: instead of an IAM role that
# Archie assume-roles, this creates a workload-identity pool that trusts Archie's
# AWS worker identity, plus a deployer SA that identity impersonates.
#
# APPLY THIS WITH YOUR OWN ADMIN CREDENTIALS (gcloud auth / your project Owner) —
# it can't run *through* Archie, because it's the thing that creates Archie's
# access. After apply, paste the three outputs into Archie
# (Settings -> Cloud Accounts -> GCP).

data "google_project" "this" {
  project_id = var.project_id
}

resource "google_project_service" "apis" {
  for_each = toset([
    "iamcredentials.googleapis.com",
    "sts.googleapis.com",
    "iam.googleapis.com",
    "cloudresourcemanager.googleapis.com",
  ])
  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

resource "google_iam_workload_identity_pool" "archie" {
  project                   = var.project_id
  workload_identity_pool_id = var.pool_id
  display_name              = "Archie"
  description               = "Keyless federation for Archie deploys"
  depends_on                = [google_project_service.apis]
}

# Trusts Archie's AWS worker account; the role ARN flows through as the
# `aws_role` attribute used in the impersonation binding below.
resource "google_iam_workload_identity_pool_provider" "aws" {
  project                            = var.project_id
  workload_identity_pool_id          = google_iam_workload_identity_pool.archie.workload_identity_pool_id
  workload_identity_pool_provider_id = var.provider_id
  display_name                       = "Archie AWS worker"
  attribute_mapping = {
    "google.subject"     = "assertion.arn"
    "attribute.aws_role" = "assertion.arn"
  }
  aws {
    account_id = var.archie_aws_account
  }
}

resource "google_service_account" "deployer" {
  project      = var.project_id
  account_id   = var.deployer_sa_id
  display_name = "Archie deployer"
}

# What Archie deploys with. Editor is the simplest starting point; scope down.
resource "google_project_iam_member" "deployer_role" {
  project = var.project_id
  role    = var.deployer_role
  member  = "serviceAccount:${google_service_account.deployer.email}"
}

# ONLY Archie's AWS worker role may impersonate the deployer SA — the keyless
# bridge. Nothing else can assume this identity.
resource "google_service_account_iam_member" "wif_impersonation" {
  service_account_id = google_service_account.deployer.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/projects/${data.google_project.this.number}/locations/global/workloadIdentityPools/${google_iam_workload_identity_pool.archie.workload_identity_pool_id}/attribute.aws_role/arn:aws:sts::${var.archie_aws_account}:assumed-role/${var.archie_worker_role}"
}
