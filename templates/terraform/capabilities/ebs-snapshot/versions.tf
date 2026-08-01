# A CAPABILITY, not infrastructure: a governed cloud-ops PRIMITIVE (take an EBS
# backup) expressed as a Terraform blueprint so it rides the exact same
# import -> classify -> govern -> publish -> deploy pipeline Archie already runs.
#
# The bridge: the worker runs `tofu apply`; the null_resource's local-exec
# provisioner shells out to the AWS CLI (already on the worker) with the deploy's
# resolved credentials. No new engine required for a first cut — the imperative
# op runs inside apply.
terraform {
  required_version = ">= 1.5"
  required_providers {
    null = {
      source  = "hashicorp/null"
      version = ">= 3.2"
    }
  }
}
