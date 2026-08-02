# gcp-archie-wif — grant Archie keyless GCP access (Workload Identity Federation)

A **one-time bootstrap** that lets Archie deploy to your GCP project **without a
service-account key**. It's the GCP mirror of the AWS `archie_role` bootstrap:
instead of an IAM role Archie assume-roles into, this creates a workload-identity
pool that trusts Archie's AWS worker identity, plus a deployer service account
that identity impersonates via short-lived tokens.

> **Why keyless:** long-lived SA keys are the #1 GCP credential-leak vector.
> Archie **does not accept SA keys** — WIF is the only supported GCP path.

## What it creates (no keys)

| Resource | Purpose |
|---|---|
| Workload Identity Pool (`archie-pool`) | Container for the external (AWS) identity |
| AWS Provider (`archie-aws`) | Trusts Archie's AWS worker account `416851285955` |
| Deployer SA (`archie-deployer@…`) | The identity Archie impersonates; holds the deploy roles |
| `workloadIdentityUser` binding | Lets **only** Archie's worker role impersonate that SA |

## How to run it (you, once, with your admin credentials)

You apply this yourself — it can't run *through* Archie, because it's what
*creates* Archie's access.

```bash
gcloud auth application-default login          # or use your admin key
terraform init
terraform apply -var="project_id=YOUR_PROJECT_ID"
```

Optional: `-var="deployer_role=roles/..."` to scope down from Editor.

## Then paste the outputs into Archie

`terraform output` prints the three **non-secret** values — Settings → Cloud
Accounts → GCP:

- `project_id`
- `deployer_sa_email`
- `wif_audience`

That's it. Archie now deploys to this project keyless. Revoke any time by
removing the `workloadIdentityUser` binding (or `terraform destroy`).
