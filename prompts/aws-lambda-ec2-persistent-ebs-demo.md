# AWS Lambda + EC2 + Persistent EBS Demo

**Cloud:** AWS
**Engine:** Terraform (works for Pulumi too — swap the syntax)
**Resources:** ~8 (Lambda, EC2 instance, persistent EBS via ebs_block_device, VPC, subnet, security group, IAM role, log group)
**Use case:** End-to-end Archie demo. Walks the full lifecycle in one stack: deploy → govern → drift → destroy → **orphan by design** → discover → resolve.

## Why this exists

The Lambda-only demo (`aws-lambda-demo.md`) shows the basic deploy + govern
loop. This one extends it so the destroy step **deliberately leaves an
orphan resource behind** — the EBS volume attached to the EC2 with
`delete_on_termination = false`. That single TF flag turns destroy into a
realistic "leftover infra" scenario, which is what Archie's discovery flow
exists to solve.

Demo arc the prompt enables:
1. Deploy → 8 resources land cleanly
2. Lock memory / required timeout → new version
3. Upgrade the existing stack to the new version
4. Induce drift on the Lambda (console) → scheduled scan catches it → remediate
5. Destroy → Lambda + EC2 gone, **EBS volume persists** in `available` state
6. Orphan scan finds the EBS volume as `tagged_orphan` ($/mo cost visible)
7. Click Adopt / Bring into Archie / Delete / Mark Intentional

## Prompt

```
Deploy an AWS Lambda function alongside a small EC2 worker with an attached EBS data volume that intentionally persists after destroy. The Lambda serves a styled HTML page (same look as the simpler Lambda demo) and the EC2 + EBS exist to demonstrate the "orphan after destroy" pattern Archie's discovery flow resolves.

Lambda (Python 3.12, architecture arm64):
- Returns HTML with background #0B0E14, message in white 42px bold centered, subtitle in gray 18px using page_title config, a "Show me another" button (rounded, 18px, white text, background from button_color config), small "askarchie.io" footer
- Each request picks one random message from this list:
  "Deploy. Detect. Remediate. All in one tool."
  "Your TF stays. We govern on top."
  "Drift detected at 2:47. Fixed at 2:48."
  "5 fields instead of 50."
  "Adopt the leftover. Or delete it. Or ignore it on purpose."
  "The PE defines the rails. Developers deploy."
  "Continuous verification, not ceremony."
- Function URL with auth type from auth_type config (default NONE)
- Memory from lambda_memory config, timeout from lambda_timeout config
- IAM role with AWSLambdaBasicExecutionRole
- CloudWatch log group with retention from log_retention_days config

Networking (minimal, single AZ):
- VPC with cidr from vpc_cidr config (default 10.42.0.0/16)
- One public subnet in us-east-1a
- Internet gateway + default route
- Security group allowing SSH (port 22) from allowed_ssh_cidrs config

EC2 worker (the disposable part):
- Single t3.nano instance using the latest Amazon Linux 2023 AMI (via aws_ssm_parameter data source on /aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64)
- Placed in the public subnet, attached to the SG
- Root volume default, gp3, 8 GiB, delete_on_termination = true
- ebs_block_device for an extra data volume:
    device_name = "/dev/sdf"
    volume_size from data_volume_size_gb config (default 5)
    volume_type = "gp3"
    delete_on_termination = FALSE  ← critical, this is what makes destroy leave the volume behind
- Tags include Role = "worker", DataResidency = "preserve-on-destroy" so the operator can see intent

Config fields:
- project_name (text, required)
- environment (select: dev/staging/production, required)
- lambda_memory (number, default 256, description "Lambda memory in MB")
- lambda_timeout (number, default 30, description "Lambda timeout in seconds")
- auth_type (select: NONE/AWS_IAM, default NONE)
- button_color (text, default #3B82F6)
- page_title (text, default "AskArchie — Lifecycle Demo")
- vpc_cidr (text, default "10.42.0.0/16")
- allowed_ssh_cidrs (list of string, default ["0.0.0.0/0"], description "CIDRs allowed SSH access; lock this in prod")
- data_volume_size_gb (number, default 5, description "Size of the persistent EBS data volume — kept after destroy")
- log_retention_days (number, default 7)

Exports: function_url, function_name, log_group_name, ec2_instance_id, ec2_public_ip, persistent_volume_id, persistent_volume_size

Provider config: aws provider only, region from environment, default_tags include Project = var.project_name, Environment = var.environment, ManagedBy = "archie"
```

## Variant for Pulumi

Drop the same prompt with the engine toggle on Pulumi. Architecture is
identical; the `delete_on_termination = false` becomes
`deleteOnTermination: false` on the `BlockDeviceMapping`. The demo arc is
the same.

## Demo script outline (8 min)

1. **AI to blueprint** (1m): prompt → generate → TF toggle → publish v1.0.0
2. **Deploy** as `lambda-ec2-one` — 8 resources land
3. **Lock + new version** (1m): lock `lambda_memory = 512`, require `lambda_timeout`, save → v1.0.1
4. **Deploy v1.0.1** as `lambda-ec2-two`, locked field disabled in the form
5. **Upgrade `lambda-ec2-one`** to v1.0.1 — fine-grained diff, one click
6. **Drift** (1.5m): modify Lambda memory or env vars via console → scheduled drift catches it → remediate
7. **Destroy `lambda-ec2-one`** — Lambda gone, EC2 terminated, **EBS persists**
8. **Discovery** — orphan scan flags the EBS (~$0.40/mo, `tagged_orphan` because the `ManagedBy:archie` tag is still on it)
9. **Resolve** — split-button menu: Adopt / Bring into Archie / Delete / Mark Intentional

Closes the loop: deploy → govern → drift → orphan-by-design → discover → reclaim.
