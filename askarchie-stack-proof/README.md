# AskArchie Stack Proof

The askarchie-quotes app, extended so the page only works when the stack is wired. Each deploy shows a quote plus a **stack proof** panel. Every hop in that panel is a real call across a wire (HTTP, SQL, AWS API, K8s API, mounted file). A hop never passes just because an env var is set. If one hop is missing, the badge turns red and names it: `BROKEN at: ECS task → RDS Postgres`.

The same app comes in three delivery forms:

| Form | Folder | Used by |
|---|---|---|
| Lambda (one zip, 3 entry points) | `lambda/` | scenarios 2, 4, 5 |
| Static site | `static/` | scenario 3 |
| Container (one image) | `container/` + `k8s/` | scenarios 1, 6 |
| Headless check (CLI) | `tools/prove.py` | 4, 5, 7, 8, and any URL |

The seed data is `common/quotes.json`, the 13 AskArchie quotes, packed with every build. Stores seed themselves on first read, so there's no separate seed step.

## What each golden path proves

| # | Golden path | Deploy as | Hops shown (all must pass) | Visible proof |
|---|---|---|---|---|
| 1 | VPC + ECS Fargate + ALB + RDS Postgres | container, `ARCHIE_STACK=alb+ecs+rds` | Internet → ALB → target · ALB target → ECS task · ECS task → RDS · RDS TLS on · RDS read/write | The views counter climbs across refreshes and tasks. Submitted quotes read back from Postgres. |
| 2 | API Gateway + Lambda + DynamoDB | `handler.api`, `ARCHIE_STACK=apigw+lambda+dynamodb` | Internet → API GW → Lambda · Lambda runtime · Lambda → DynamoDB · read/write | Same counter and submit form, stored in DynamoDB |
| 3 | S3 + CloudFront | upload `static/index.html` + `static/quotes.json` | HTTPS · Browser → CloudFront edge (x-amz-cf-pop) · CloudFront → S3 origin (server AmazonS3) | Page + `prove.py static --s3-url` shows direct S3 is refused (OAC) |
| 4 | SQS + Lambda consumer + DynamoDB | `handler.consumer` on the queue | Standalone: `prove.py sqs` sends a probe + 5 quotes and waits for them in the table. Composed with 2 (`+sqs`), the page's submit form goes through the queue. | Submissions show "queue · 190 ms queue→store" |
| 5 | EventBridge schedule + Lambda | `handler.schedule` as the rule target | Standalone: `prove.py schedule` checks rule → target, ENABLED, and a logged *scheduled* run. Composed with 2 (`+schedule`), the page shows "Quote of the hour". | Manual invokes never count; only `source: aws.events` does |
| 6 | VPC + KMS + EKS + workload | container + `k8s/manifest.yaml`, `ARCHIE_STACK=eks+configmap` | Service → Pod → K8s API (service account + RBAC) · Pod → ConfigMap (quotes are mounted, not baked in) | `prove.py eks` adds the control plane in the VPC and secrets encrypted with *the composed* KMS key |
| 7 | VPC foundation | nothing to deploy | `prove.py vpc`: subnets span ≥2 AZs · public → IGW · private → NAT, with the NAT in a public subnet | Route tables are the wiring |
| 8 | KMS key | nothing to deploy | `prove.py kms`: key enabled, rotation, encrypt → decrypt round trip of a quote | |

The best demo is 2+4+5 on one page (`ARCHIE_STACK=apigw+lambda+dynamodb+sqs+schedule`): API, function, table, queue, consumer and schedule, all green, and a quote a viewer types comes back through the queue.

## The wiring contract (what Archie's wiring must inject)

This is the check on capability wiring. Each value below has to come from another resource's output. If it's wired to the wrong thing, the matching hop goes red.

| Env | From | Scenario |
|---|---|---|
| `ARCHIE_STACK` | the golden path itself (declared, not wired) | all app forms |
| `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER` | RDS module outputs (`PostgresEndpoint`) | 1 |
| `DB_PASSWORD` | ECS task `secrets.valueFrom` → Secrets Manager (`Secret`) | 1 |
| `TABLE_NAME` (+ `TABLE_KEY`, default `pk`, string hash key) | DynamoDB table output | 2, 4, 5 |
| `QUEUE_URL` | SQS output (`Queue`) → the API Lambda, only when composed with 4 | 2+4 |
| SQS event source mapping, `ReportBatchItemFailures` on | queue ARN → consumer function | 4 |
| EventBridge rule target | rule → `handler.schedule` ARN | 5 |
| `QUOTES_FILE`, `POD_NAME`, `NODE_NAME` | ConfigMap mount + downward API (in the manifest) | 6 |

IAM the functions/tasks need: DynamoDB `GetItem, PutItem, UpdateItem, Scan` (+ `DescribeTable` to show encryption), `sqs:SendMessage` for the API Lambda when `+sqs`, and the standard SQS consumer permissions for the consumer. When the table uses a customer KMS key, add `kms:Decrypt`/`GenerateDataKey` on that key. A missing permission fails a hop, which is the point.

## Smoke test hook

`GET <url>/?format=json` returns the proof as JSON: **HTTP 200 when every hop is wired, 503 when broken**, with `broken_at`. `prove.py` exits 0/1. A golden-path smoke test can assert serving *and* wiring with one call:

```
python3 tools/prove.py url https://<alb-or-api-url>/
python3 tools/prove.py static --url https://dxxxx.cloudfront.net --s3-url https://<bucket>.s3.amazonaws.com
python3 tools/prove.py sqs --queue-url <url> --table <name>
python3 tools/prove.py schedule --function <name>
python3 tools/prove.py eks --cluster <name> --kms-key-arn <arn> --url http://<svc>/
python3 tools/prove.py vpc --vpc-id vpc-...
python3 tools/prove.py kms --key-id alias/...
```

The CLI uses the normal AWS credential chain. Never pass keys as arguments.

## Build

- Lambda: `sh lambda/build.sh` → `lambda/dist/askarchie-stack-proof-lambda.zip`. No dependencies (boto3 is in the runtime). Handlers are `handler.api`, `handler.consumer` and `handler.schedule`.
- Container: `docker build -f container/Dockerfile -t askarchie-stack-proof .` from this folder. Adds `pg8000` (pure Python) and the RDS CA bundle so the TLS hop is verified. Health checks at `/health`, `/healthz` and `/ping` stay shallow, so the target stays healthy while you look at the red hop. The deep check is `?format=json`.
- Static: upload `static/` to the bucket, with `index.html` as the default root object.

## Notes

- Scenario 1's health check stays green even when RDS is unreachable. That's deliberate: a dead task hides *which* wire broke, and the proof panel names it.
- The queue probe (`?format=json` and every page load with `+sqs`) writes a small `marker#probe-*` item per check. Add a TTL on the table if it runs often.
- The EKS image ships a copy of quotes.json but never reads it. It reads only the ConfigMap mount, so a missing mount fails the hop instead of falling back.
