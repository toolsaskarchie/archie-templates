# AWS Lambda Demo — Interactive Page

**Cloud:** AWS
**Resources:** ~4 (Lambda function, Function URL, IAM role, CloudWatch log group)
**Use case:** Live demo / talk demo. Public Function URL serves a styled HTML
page that randomly displays one of 10 platform-engineering messages on each
refresh. Page title + button color are configurable.

## Why this exists

The single most reliable demo path for an Archie agent → AI codegen → deploy
loop. Small enough to deploy in ~30s, visible enough to show governance edits
(button color, page title, message list) reflected end-to-end.

## Prompt

```
Deploy a Lambda function with a public Function URL that serves a styled HTML page. Each request randomly displays one of these messages:

"Governance in the deploy path, not around it"
"5 fields instead of 50"
"Drift detected. One click to fix."
"The developer deploys. The PE defines the rules."
"Your Terraform stays. We govern on top."
"Deploy blocked: unresolved drift. Remediate first."
"9 resources. 10 config fields. One click."
"The real complexity starts the day after deploy."
"Detection is solved. The gap is between detected and fixed."
"Describe. Generate. Govern. Deploy."

The Lambda (Python 3.12) returns HTML with:
- Background color #0B0E14
- Message in white (#F1F5F9), bold, 42px, centered vertically and horizontally
- Subtitle below in gray (#64748B), 18px, using the page_title config value
- A "Show me another" button that reloads the page, rounded corners, 18px, white text, background color from button_color config
- Below the button in small gray text: "askarchie.io"
- The HTML page title uses the page_title config value
- Viewport meta tag for mobile
- Response headers: Content-Type text/html, no caching

Infrastructure:
- Lambda function Python 3.12, memory from lambda_memory config, timeout from lambda_timeout config, architecture arm64
- Lambda Function URL with auth type from auth_type config (NONE for public, AWS_IAM for authenticated)
- IAM role with AWSLambdaBasicExecutionRole policy
- CloudWatch log group /aws/lambda/{project}-{env}-archie-demo with retention from log_retention_days config

Config fields: project_name (text, required), environment (select: dev/staging/production, required), lambda_memory (number, default 256, description "Lambda memory in MB"), lambda_timeout (number, default 30, description "Lambda timeout in seconds"), auth_type (select: NONE/AWS_IAM, default NONE, description "Function URL authentication type"), button_color (text, default #3B82F6, description "Hex color for the refresh button"), page_title (text, default "AskArchie — Cloud Standards Platform", description "Page title and subtitle text"), log_retention_days (number, default 7, description "CloudWatch log retention in days")

Exports: function_url, function_name, log_group_name

Implementation requirement (critical to avoid runtime errors): pass page_title and button_color into the Lambda via environment.variables, and read them at runtime with os.environ.get(...). The handler_code variable in the Pulumi code must be a plain triple-quoted string (no f prefix) — do NOT use handler_code = f'''...'''. Inside the handler, use a single f-string only at the moment of rendering the HTML response. This avoids nested f-strings, which produce 502s due to brace-escape miscounts.

Expected: single preview pass, 3-4 resources.
```

## Demo edit prompts

After deploying the blueprint, these edit prompts are validated for the
"governance + AI iteration" demo flow.

**Add a new phrase + change button color (single-pass edit):**

```
Hazme dos cambios:
1. Agrega una frase #11 al final de la lista de mensajes: 'Built at AWS UG Querétaro 🚀'
2. Cambia el color del botón a morado
```

**Notes for live demo:**
- The button color change takes effect on the next deploy (env var update is
  enough — no Lambda code redeploy required if the env-var pattern is in place)
- The new phrase requires redeploying the Lambda (it's hardcoded in the
  `MESSAGES` list inside `handler_code`)
- Refresh the Lambda Function URL ~10× to see the new phrase in rotation
  (random.choice over 11 items = ~9% chance per refresh)
- Avoid asking for hex codes in the edit prompt — use natural color names
  ("morado", "azul", "rojo"). The AI handles natural color names more reliably
  than mechanical hex swaps inside f-strings

## Verifying the deploy

After Studio publishes the blueprint and you trigger a deploy:

1. Watch the deploy modal until COMPLETED (~30s for this stack)
2. Hit the `function_url` output in a browser → expect HTTP 200 with the
   styled page rendering
3. Refresh a few times to see different messages in rotation
4. (Demo bonus) Inject drift via console — change Lambda memory from 256 to
   512 — then run drift detection / remediation to show the full lifecycle

## When this prompt stops working

If a fresh generation produces broken code:

1. Check whether the AI generated a nested-f-string handler (search for
   `handler_code = f'''` in the generated `pulumiCode`). If yes, the
   "Implementation requirement" paragraph at the end of the prompt was either
   ignored or weakened — re-emphasize it.
2. Check whether the AI used `.format()` instead of `os.environ.get` for
   `page_title` / `button_color`. The env-var pattern is the only one that
   reliably survives across regenerations.
3. Re-run with Studio settings: `temperature: 0` (set on
   `/api/studio/generate` and `/api/studio/edit`).
