# Demo: lambda-app — "govern the config" opener

A thin Lambda app consuming the pinned `pattern3-aws/modules/lambda` module. Fast to deploy; its outputs echo the **effective governed values**, so non-prod vs prod differences are visible in the stack drawer.

## The demo beat (≈2 min)
1. **Import** this folder as a blueprint in Archie Studio (`templates/terraform/demo/lambda-app`).
2. **Govern** — on the **production** profile, lock these fields to the `prod.tfvars` values:
   | Field | Non-prod | Prod (locked) |
   |---|---|---|
   | `lambda_memory` | 256 | **1024** |
   | `lambda_timeout` | 15 | **30** |
   | `log_retention_days` | 7 | **90** |
   | `reserved_concurrency` | 0 | **50** |
   | `enable_xray` | false | **true** |
   | `enable_dlq` | false | **true** |
3. **Deploy** to non-prod → fast. Open the stack drawer: outputs show `memory_size_mb=256`, `tracing_enabled=false`.
4. **Deploy** to prod (or upgrade the env) → outputs now show `memory_size_mb=1024`, `tracing_enabled=true`, `dlq_enabled=true` — **the locked floor was enforced**, even if a dev tried lower values.

## Talking point
The app exposes a clean, small lever set — that's the governance surface. Archie locks exactly these per profile; a developer can't ship an under-provisioned, untraceable Lambda to prod.

> Module pinned to commit `4903fd3c…`. No backend/provider block — Archie injects them. Switch `?ref=` to a `v1.0.0` tag once you cut a release.
