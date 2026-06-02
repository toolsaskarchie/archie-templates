# #4 — Azure Function App (Pulumi)

Pulumi mirror of [#3](../../terraform/function-app/README.md). Same
resources, same conditional gates, same HTML page (deployed via app settings
+ FUNCTIONS_WORKER_RUNTIME=python).

Note: the handler code is loaded at first invocation from the function app's
Azure Files share. For the test panel the focus is the IaC lifecycle, not
the function payload — the HTTP endpoint returns a default Azure Functions
landing page until handler code is deployed (azure functions core tools
or zip deploy). The `function_url` output is still meaningful for drift
testing because the App settings `PAGE_TITLE` / `BUTTON_COLOR` will surface
in any deployed handler.

## Resource counts

| Profile  | Count |
|----------|-------|
| Non-prod | 5     |
| Prod     | 7 (+App Insights, +slot marker = +2) |

## Profiles

Same lock vocabulary as [#3](../../terraform/function-app/README.md#profiles).
Pulumi config keys mirror the TF variable names.
