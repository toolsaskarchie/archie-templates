# OD-6 Orphan Test Fixture

A self-contained Terraform/OpenTofu project that creates 10 AWS resources
designed to exercise every code path in Archie's Cloud Discovery + Delete
Orphan Resources flow (OD-6 Pass 1 + Pass 2).

## What it creates

| # | Resource | Purpose |
|---|----------|---------|
| 1 | DynamoDB table (no protection) | Happy-path delete |
| 2 | DynamoDB table (deletion-protected) | `hard_blocker` test |
| 3 | Lambda function (no event sources) | Clean delete |
| 4 | SNS topic with 1 subscription | Warning test ("N subscription(s) will be deleted") |
| 5 | SQS queue (empty) | Clean delete |
| 6 | S3 bucket (empty) | Happy path — no `force_empty` checkbox |
| 7 | S3 bucket (versioned + non-empty) | `force_empty` flow + paginated batch-delete |
| 8 | EC2 t3.nano (no protection) | Clean terminate |
| 9 | EC2 t3.nano (termination-protected) | `hard_blocker` test |
| 10 | EC2 t3.nano + persistent EBS | Warning test ("EBS will persist as orphan") |

Plus supporting infra: 1 VPC, 1 subnet, 1 IAM role for Lambda.

## Why apply directly (not via Archie)

If you deploy via Archie UI, the OD-0 stack-transformation stamps
`ManagedBy: Archie` on every resource. Those resources scan as `managed`,
not orphan — defeats the test.

Apply via the CLI with `terraform apply` to land them **untagged**, so an
Archie scan from the same account classifies all of them as `unmanaged`
orphans — which is what we want to test the destroy flow against.

## Usage

```bash
# Pick the AWS account you want to litter — CloudGuru sandbox is ideal,
# the fixture stays under $0.20/hr (3× t3.nano).
export AWS_PROFILE=cloudguru
terraform init
terraform apply -auto-approve
```

Then in Archie:

1. Go to **/import** (Cloud Discovery)
2. Save the same AWS creds as a Cloud Account (or paste inline)
3. Scan us-east-1
4. The 10 test resources show up as `unmanaged` orphans
5. Click into each, exercise the Delete flow, verify expected modal behavior

## Cleanup

```bash
terraform destroy -auto-approve
```

If you already deleted some resources via Archie OD-6, `terraform destroy`
will skip those with "already destroyed" — no error.
