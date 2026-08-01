# Capability: EBS Snapshot — Terraform (AWS)

A **governed cloud-ops capability**, not infrastructure. Instead of a Jenkins job
or a one-off `aws ec2 create-snapshot`, the op is a blueprint: import it, govern
its parameters, and run it through Archie with an audit trail — the operator never
holds cloud credentials.

## How it works (no new engine)

It's a thin Terraform wrapper: a `null_resource` whose `local-exec` provisioner
runs the AWS CLI (already present on the worker) during `tofu apply`, with the
deploy's resolved credentials. So it rides the existing import → classify →
govern → publish → deploy pipeline unchanged. The pure "script engine" is the
cleaner long-term design; this proves the model today.

## Parameters (classified like any blueprint's config fields)

| Name | Default | Role |
|---|---|---|
| `volume_id` | _(required)_ | The EBS volume to snapshot (`vol-…`) — operator supplies |
| `region` | `us-east-1` | Region the volume lives in — a PE can **lock** this |
| `description` | `archie-capability: on-demand EBS backup` | Snapshot label — governed |

## Outputs

| Name | What |
|---|---|
| `capability` | `ebs-snapshot` |
| `target_volume` | The volume it snapshotted |
| `region` | Region it ran in |

## Run it via Archie

1. Import: `import_terraform(name="ebs-snapshot", path="templates/terraform/capabilities/ebs-snapshot")`
2. It lands as a **draft** with `volume_id` free and `region`/`description` governed.
3. Govern (lock `region`), verify, publish.
4. Deploy with a `volume_id` → the worker runs `tofu apply` → the snapshot is created in the operator's account.
