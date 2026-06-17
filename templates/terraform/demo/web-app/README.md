# Demo: web-app — the drift → remediate security showpiece

ALB + EC2 + VPC + security groups, via the pinned `pattern3-aws/modules/web-modular` module. The governance star is **`allowed_cidrs`** (who can reach the ALB). This is the demo that lands.

## Govern (per profile)
| Field | Non-prod | Prod (locked) |
|---|---|---|
| `instance_type` | t3.micro | **t3.large** |
| `ec2_instance_count` | 1 | **3** |
| `allowed_cidrs` | `0.0.0.0/0` (sandbox) | **corporate CIDR only** |
| `vpc_cidr` | 10.40.0.0/16 | 10.50.0.0/16 |

## The money-shot beat (≈3 min)
1. **Import** `templates/terraform/demo/web-app` as a blueprint; **Govern** the prod profile to lock `allowed_cidrs` to your corporate CIDR.
2. **Deploy** → open the `alb_url` output, the app loads. Note `alb_security_group_id` in the drawer.
3. **Break it like a human would:** in the AWS console, add an inbound rule to that ALB security group — `0.0.0.0/0` on port 22 (or 0–65535). (This is the classic "someone opened it up at 2am" scenario.)
4. **Run drift** in Archie → the stack flips to **DRIFTED**, P-severity, showing `ingress: expected <locked CIDR> | actual 0.0.0.0/0`.
5. **Remediate** in Archie → it re-applies the blueprint, the rogue rule is removed, stack returns to **in-sync**. Governance enforced *after* the fact, not just at deploy.

## Why this sells
It's the whole pitch in one motion: you **locked** the access policy, a human **violated** it out-of-band, Archie **detected** it and **put it back** — without anyone writing a ticket. The ALB also gives a clickable URL so the audience sees a real running app, not just a plan.

> Module pinned to commit `4903fd3c…`. No backend/provider block — Archie injects them. `allowed_cidrs` default is closed; the open value is explicit in `nonprod.tfvars`. Switch `?ref=` to a `v1.0.0` tag once you cut a release.
