# The capability body. On `tofu apply` the local-exec provisioner runs the AWS
# CLI with the deploy's credentials (env-injected by the worker) — the same creds
# path a normal deploy uses, so the op runs in the operator's account, never
# Archie's. Params are passed as ENV (not string-interpolated into the shell) so
# a value can't break out of the command.

resource "null_resource" "ebs_snapshot" {
  # Re-runs the op whenever a param changes (a fresh apply = a fresh snapshot).
  triggers = {
    volume_id   = var.volume_id
    region      = var.region
    description = var.description
  }

  provisioner "local-exec" {
    interpreter = ["/bin/sh", "-c"]
    environment = {
      VOL  = var.volume_id
      RGN  = var.region
      DESC = var.description
    }
    command = <<-EOT
      set -e
      echo "[capability:ebs-snapshot] creating snapshot of $VOL in $RGN"
      aws ec2 create-snapshot \
        --volume-id "$VOL" \
        --region "$RGN" \
        --description "$DESC" \
        --tag-specifications 'ResourceType=snapshot,Tags=[{Key=archie:capability,Value=ebs-snapshot}]'
    EOT
  }
}

output "capability" {
  value = "ebs-snapshot"
}

output "target_volume" {
  value = var.volume_id
}

output "region" {
  value = var.region
}
