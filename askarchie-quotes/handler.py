"""AskArchie random-quote endpoint.

Returns a different quote about AskArchie on every request, so refreshing the
public URL (API Gateway -> Lambda) shows a new one each time. No dependencies,
so no Lambda layer is needed.
"""

import random

# Quotes drawn from AskArchie's own messaging (askarchie.io).
QUOTES = [
    "Agents provision. Archie governs. You ship.",
    "A whole platform team's output — from one person who owns the rules.",
    "You don't author infrastructure by hand. You ask.",
    "No Terraform. No fifty-variable forms. No ten-tool stack to assemble.",
    "A request goes in; a governed golden path comes out.",
    "One person owns the rules — Archie is the platform team you didn't have to hire.",
    "Archie reuses what you already have before it writes anything new.",
    "The golden path is the only route to your cloud.",
    "Your cloud keys live in Archie, never in a session.",
    "A platform engineer composes a golden path once; developers consume it forever.",
    "Deploy, drift, remediate, upgrade, roll back, destroy — one loop, with a receipt.",
    "Checked before anything is built.",
    "Governance fires on what the modules create, not on what someone remembered.",
]


def _page(quote: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AskArchie — a quote</title>
  <style>
    :root {{ color-scheme: light dark; }}
    body {{
      margin: 0; min-height: 100vh; display: grid; place-items: center;
      font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
      background: #0b0d12; color: #e8eaf0;
    }}
    figure {{ max-width: 40rem; padding: 2rem; text-align: center; }}
    blockquote {{ font-size: clamp(1.4rem, 4vw, 2.2rem); line-height: 1.3; margin: 0 0 1rem; }}
    figcaption {{ opacity: .6; letter-spacing: .08em; text-transform: uppercase; font-size: .8rem; }}
    a {{ color: inherit; }}
  </style>
</head>
<body>
  <figure>
    <blockquote>&ldquo;{quote}&rdquo;</blockquote>
    <figcaption>AskArchie &middot; refresh for another</figcaption>
  </figure>
</body>
</html>"""


def handler(event, context):
    quote = random.choice(QUOTES)
    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "text/html; charset=utf-8",
            # no-store so each refresh re-invokes and shows a fresh quote
            "Cache-Control": "no-store",
        },
        "body": _page(quote),
    }
