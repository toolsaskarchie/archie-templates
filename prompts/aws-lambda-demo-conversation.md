# AskArchie Lambda Demo — Full Agent Conversation

The complete chat-driven flow for a governed Lambda deploy: list → deploy with governance override → drift detection → remediation preview → apply → verify in-sync.

This is the conversation that goes with the [aws-lambda-demo](./aws-lambda-demo.md) prompt.

---

## 1. Deploy Flow

### What blueprints do we have?

> **User:** what lambda blueprints do we have

> **Archie:** Here are the lambda blueprints available in your company's governed catalog:
>
> **AWS Lambda Blueprints:**
>
> - **New Lambda Demo Page** (`bp-mou7h0ttjpge0g`)
>   - Base template: `aws-newlambda-demo-nonprod`
>   - Engine: Pulumi (v1.1.2)
>   - 3 locked fields (governed settings)
>   - Description: Lambda function with public Function URL serving a styled HTML page with random motivational messages
>
> - **Legacy Claims API Simulator** (`bp-mo4jklu4mtviu9`)
>   - Base template: `aws-legacy-claims-api-nonprod`
>   - Engine: Pulumi (v1.1.4)
>   - No locked fields
>   - Description: Lambda function simulating a legacy insurance claims API with random latency
>
> - **Interactive Lambda Demo Page** (`bp-mou1bywzo0dmbv`)
>   - Base template: `aws-lambda-demo-nonprod`
>   - Engine: Pulumi (v1.1.0)
>   - 3 locked fields (governed settings)
>   - Description: Lambda function with public Function URL serving styled HTML with motivational messages
>
> These are your **company's governed blueprints** — they're customized and approved by your platform team. The locked fields ensure compliance with your organization's standards.
>
> Would you like me to show you the detailed configuration for any of these lambda blueprints, or would you like to see what starter library templates are also available?

### Deploy with conflicting config

> **User:** deploy New Lambda Demo Page with 512 memory and 30 days log retention

> **Archie:** ⚠️ **Governance Policy Conflicts:**
>
> - **Log Retention:** You requested 30 days, but this blueprint locks it to 7 days
> - **Lambda Memory:** You requested 512 MB, but this blueprint locks it to 256 MB
>
> The locked values from your platform team will take precedence. Would you like to:
>
> 1. Deploy with the governed values (256 MB memory, 7 days retention)
> 2. Request an exception from your platform team to unlock these fields
> 3. Choose a different blueprint that allows these configurations
>
> If you want to proceed with option 1, I'll need you to provide:
> - Project name (default: `archie-demo`)
> - Stack name (format: `{project}-{service}-{env}`)
>
> The other fields have reasonable defaults that we can use.

### Confirm with project name

> **User:** yes proceed project name, app name and stack name archieisgreat

> **Archie:** ✅ **Deployment Started Successfully!**
>
> **Deployment Details:**
> - Deployment ID: `deploy-1778089590652`
> - Stack Name: `archieisgreat-archieisgreat-dev`
> - Project: `archieisgreat`
> - App Group: `archieisgreat`
> - Environment: `dev`
> - Status: `QUEUED`
>
> **Applied Governance Settings:**
> - Lambda Memory: **256 MB** (governance-locked, overrode your 512 MB request)
> - Log Retention: **7 days** (governance-locked, overrode your 30 days request)
>
> **Your Configuration:**
> - Auth Type: `NONE`
> - Button Color: `#22C55E`
> - Page Title: "AskArchie — Cloud Standards Platform"
> - Lambda Timeout: 30 seconds
> - Region: `us-east-1`
>
> The deployment is now queued and will begin provisioning shortly. The governance policies ensured compliance with your organization's standards while using your specified project naming.

---

## 2. Drift Detection

> **Archie:** **ACKNOWLEDGED DRIFT** (Known / Monitored)
> - `archie-orchestrator` — 3 drifted (acknowledged)
> - `archie-auditor` — 3 drifted (acknowledged)
> - `archie-planner` — 3 drifted (acknowledged)
>
> **Priority Recommendation:** The `archie-triage` stack (3 drifts) and your recent Lambda deployment `archieisgreat-archieisgreat-dev` (2 drifts) need immediate investigation.
>
> Would you like me to:
> - Check detailed drift on the Lambda stack (`archieisgreat-archieisgreat-dev`)?
> - Investigate `archie-triage` drift?
> - Preview remediation for any of these stacks?
>
> Which stack should I investigate first? 🔍

---

## 3. Remediation Preview

> **User:** remediate archieisgreat-archieisgreat-dev

> **Archie:** 🔧 **REMEDIATION PREVIEW**
>
> **Stack:** `archieisgreat-archieisgreat-dev` (`deploy-1778089590652`)
>
> This will restore **2 resources** to their blueprint-defined state:
>
> **IAM Role** — `archieisgreat-archieisgreat-dev-lambda-role`
> - Remove unauthorized `AWSLambdaBasicExecutionRole` managed policy
> - Restore to blueprint permissions only
>
> **Lambda Function** — `archieisgreat-archieisgreat-dev-function`
> - Reset memory from **512 MB → 256 MB** (as defined in blueprint)
> - Restore original function code (overwriting manual changes)
> - Reset deployment package to blueprint version
>
> ⚠️ **Warning:** This will overwrite any manual code changes made to the Lambda function.
>
> Do you want me to apply this fix? (Type `yes`, `fix it`, `go`, or `proceed` to confirm)

---

## 4. Apply Remediation

> **User:** yes

> **Archie:**
> ✓ Routing your request...
> ✓ Routing to Triage...

> **Archie:**
> **Stack:** `archieisgreat-archieisgreat-dev` (`deploy-1778089590652`)
> **Status:** Remediating 2 resources
>
> - IAM Role: `archieisgreat-archieisgreat-dev-lambda-role`
> - Lambda Function: `archieisgreat-archieisgreat-dev-function`
>
> The stack is now being restored to its blueprint-defined state. These unauthorized cloud changes are being reverted to match your infrastructure configuration.
>
> **Next Steps:** The remediation is in progress. You can monitor the Deployments page for completion status.

---

## 5. Verify In-Sync

> **User:** status?

> **Archie:** ✅ **DRIFT REMEDIATION SUCCESSFUL!**
>
> **Stack:** `archieisgreat-archieisgreat-dev` (`deploy-1778089590652`)
>
> **📊 Current Status**
> - Deployment Status: **COMPLETED** ✅
> - Drift Status: **in_sync** ✅
> - Drifted Resources: **0** (previously had 2)
> - Last Drift Check: Just completed (`1778094626`)
>
> **🔧 Remediation Results**
> The drift remediation has been **successfully applied**! Both resources that were previously drifted are now back in sync:
>
> - IAM Role: `archieisgreat-archieisgreat-dev-lambda-role-2b8653d` — ✅ Restored
> - IAM Role Policy Attachment: `archieisgreat-archieisgreat-dev-lambda-policy` — ✅ Restored
>
> **📋 All Resources Status**
> All 5 resources in the stack are now deployed and in sync:
>
> - CloudWatch Log Group ✅
> - IAM Role ✅
> - IAM Role Policy Attachment ✅
> - Lambda Function ✅
> - Lambda Function URL ✅
>
> 🎉 The stack is now fully compliant with its blueprint configuration. No further action needed.

---

## What just happened

In this conversation:

1. **Discovery** — Asked the agent for a list of Lambda blueprints. It returned the company-governed catalog (`bp-XXX` IDs, locked-field counts, base template names) — not random starter-library templates. Governance-first.
2. **Governance enforcement** — Requested 512 MB memory + 30-day retention. The agent compared against the blueprint's locked fields, surfaced both conflicts, and offered three options instead of silently overriding or silently complying.
3. **Confirmed deploy** — Picked option 1 (governed values) with a project name. The agent fired the deploy with the locked values winning over the user's requested values, returning a real `deploy-XXX` ID.
4. **Drift detection** — Drift was already detected on the stack (someone manually changed the Lambda outside Archie). The agent listed drifted stacks with severity priorities.
5. **Remediation preview** — Asked to remediate. The agent showed which resources would be restored, what specifically would change (memory 512 → 256, role policy removal), and warned about overwriting manual changes — before doing anything.
6. **Apply** — Single `yes` confirmation. Routed to Triage agent. Real Pulumi `up` against the existing stack with `is_remediation=true`.
7. **Verify** — Status check returned `in_sync` with all resources back to the blueprint state.

Total: 5 user turns. The governance, planning, confirmation token enforcement, and verification all happen in the agent layer — no UI clicks, no YAML edits, no config files. The locked fields exist in the blueprint, the agent honors them automatically.

---

## Try it yourself

1. Use the [aws-lambda-demo](./aws-lambda-demo.md) prompt to seed the blueprint
2. Publish from Studio with locked fields on `lambda_memory` and `log_retention_days`
3. Open the chat panel and run through the conversation above with your own project name
