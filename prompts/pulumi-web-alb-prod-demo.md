# Pulumi Web Stack (ALB + EC2 + VPC) — Prod Demo

**Cloud:** AWS
**Engine:** Pulumi (Python)
**Resources:** ~12 (VPC, 2 public subnets, IGW + route table, ALB + listener + target group, ALB SG, backend SG, EC2 instances, IAM instance profile)
**Entry point:** Studio → **Generate**. Pulumi counterpart to the Terraform `templates/terraform/demo/web-app` (which enters via Studio → **Import**). The drift → remediate security showpiece, on the Pulumi engine.

## Why this exists

The "money-shot" governance beat — lock who can reach the app, let a human open it up out-of-band, watch Archie detect and revert — should work on **both** engines to prove governance is engine-agnostic. TF enters by import; Pulumi enters by AI generate. Same story.

## Demo arc

1. Studio → Generate → paste prompt → Verify → blueprint with a rich config schema.
2. **Govern**: on prod, lock `instance_type` t3.large, `ec2_instance_count` 3, and especially `allowed_cidrs` to your corporate CIDR. Non-prod allows `0.0.0.0/0` so the app is clickable.
3. Deploy → open the `alb_url` output, the app loads. Note `alb_security_group_id`.
4. **Break it like a human:** add an inbound `0.0.0.0/0` rule to that ALB SG in the AWS console.
5. **Drift check** → DRIFTED, P-severity, `ingress: expected <locked CIDR> | actual 0.0.0.0/0`.
6. **Remediate** → Archie re-applies the blueprint, the rogue rule is removed, stack back to in-sync.

## Prompt

```
Generate an AWS web application stack using Pulumi with Python (pulumi and pulumi_aws). Production-grade and fully governable — every lever is a config field a platform engineer can lock per environment. This stack exists to demonstrate locking network access and remediating drift.

Resources:
- VPC with cidr_block from vpc_cidr config; enable DNS hostnames + support
- Two public subnets across two AZs (us-east-1a, us-east-1b), map_public_ip_on_launch true
- Internet gateway + a public route table (0.0.0.0/0 -> igw) associated to both subnets
- ALB security group: ingress on port 80 (and 443 when enable_https) FROM allowed_cidrs config only; egress all. THIS is the resource the drift demo edits.
- Backend security group: ingress on target_port ONLY from the ALB security group; egress all
- Application Load Balancer (internet-facing unless internal config is true) across both public subnets, in the ALB SG
- Target group on target_port (HTTP), health check path "/"
- HTTP listener on 80 forwarding to the target group
- EC2 instances: count from ec2_instance_count config, instance_type from instance_type config, latest Amazon Linux 2023 AMI (SSM parameter /aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64), in the backend SG, user_data installs httpd and serves a simple page showing the hostname; register each instance with the target group
- IAM instance profile + role (assume-role ec2.amazonaws.com, attach AmazonSSMManagedInstanceCore for SSM access — no SSH key)
- Standard tags on every resource: Project from project_name, Environment from environment, ManagedBy = "Archie"

Config fields (these become the govern schema — keep names and types exact):
- project_name (text, required, description "Resource name prefix. PE-locked.")
- environment (select: nonprod/prod, required, description "Drives the governance profile.")
- vpc_cidr (text, default "10.40.0.0/16", description "VPC CIDR. Profile lever.")
- instance_type (text, default "t3.micro", description "EC2 size. Profile lever — nonprod t3.micro, prod locked larger.")
- ec2_instance_count (number, default 1, description "Backend instances behind the ALB. Profile lever — prod >=3 for HA.")
- allowed_cidrs (list of string, default ["10.0.0.0/8"], description "CIDRs allowed to reach the ALB. LOCK THIS per profile — the drift/remediate star. nonprod opens 0.0.0.0/0, prod corporate CIDR only.")
- target_port (number, default 80, description "Backend listener port.")
- internal (bool, default false, description "Internal-only ALB (no public IP).")
- enable_https (bool, default false, description "Terminate HTTPS on the ALB (requires certificate_arn).")
- certificate_arn (text, default "", description "ACM cert ARN when enable_https is true.")

Exports: alb_url, alb_dns_name, alb_security_group_id, instance_ids, instance_type, instance_count, vpc_cidr

Provider: aws only, region resolved from the deploy environment. Do NOT hardcode credentials or a backend — Archie injects them.

Implementation requirements:
- allowed_cidrs is the security star: the default in the schema is closed (private RFC1918); the wide-open 0.0.0.0/0 is a per-env value the operator sets for non-prod, never the default.
- Make enable_https conditional (only add the 443 ingress + HTTPS listener when true and a certificate_arn is provided).
- No nested f-strings; build user_data with a plain string + .format() to avoid brace-escape bugs.
- Must deploy with no overrides (every config has a sane default).
```

## Notes

Heavier than the serverless prompt (more resources, longer deploy) — it routes to Fargate in Archie. **Verify it deploys before demoing**, and publish the verified output as a catalog blueprint so the live demo doesn't depend on a fresh generation. Update this file if a model/system-prompt change breaks it (per `prompts/README.md`).
