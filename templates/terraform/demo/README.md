# Demo — Governing Existing Terraform with Archie

Two **demo-ready, version-pinned** Terraform apps for showing Archie govern existing TF end to end: **import → govern (lock fields per env) → deploy → drift → remediate**.

Both are thin "app" roots that consume the reusable `pattern3-aws` modules **pinned to an immutable commit** (so a live demo is deterministic — the module can't change under you mid-demo).

## Which to use

| App | Best for | The beat |
|---|---|---|
| [`lambda-app/`](lambda-app/) | the fast opener | Lock `lambda_memory` / `lambda_timeout` / `log_retention_days` / `reserved_concurrency` per env. Non-prod 256 MB, **prod locked to 1024 MB**. Deploys in seconds; outputs echo the effective (governed) values. |
| [`web-app/`](web-app/) | the showpiece | ALB + EC2 + security groups. Lock `allowed_cidrs`. Then hand-edit the SG in the AWS console to add `0.0.0.0/0` → run **drift** (DRIFTED) → **remediate** (reverted). The security-governance money shot. |

Recommended flow for a full demo: **lambda-app first** (quick "we govern the config"), then **web-app** (the drift→remediate security story).

## How it maps to Archie

These roots intentionally have **no `backend {}` or `provider {}` block** — Archie's native-TF engine injects the S3 backend, providers, and tenant credentials at deploy time (see `archie-backend/docs/LIFECYCLE_ACTIONS.md` §5.2). So a demo app = *module call + governable inputs*, and Archie supplies the plumbing.

Govern in Archie's Studio **Govern** step: import the repo, browse to `templates/terraform/demo/<app>`, then lock the fields listed in each app's README per profile (non-prod / production).

## ⚠️ The pin

Modules are pinned to commit `4903fd3c8825d505001cb47e35a26385e418e7a8` via `?ref=<sha>`. This is immutable and demo-safe **now**. When you cut a release, tag the repo (`git tag v1.0.0 && git push --tags`) and switch the `?ref=` in each `main.tf` to `?ref=v1.0.0` for readability — and you get a second governance talking point: *"Archie pins the module version, not just the config."*

## Per-env values

Each app ships `nonprod.tfvars` and `prod.tfvars` showing the values you'd lock per profile. Variable **defaults are closed/safe**; the wide-open demo value (`allowed_cidrs = 0.0.0.0/0`) only appears explicitly in `nonprod.tfvars`.
