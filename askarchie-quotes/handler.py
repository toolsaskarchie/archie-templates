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
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after {{ box-sizing: border-box; }}

    :root {{
      --bg:        #0b0d18;
      --surface:   #12152a;
      --border:    #1e2340;
      --accent:    #5c5af6;
      --accent-glow: rgba(92, 90, 246, 0.25);
      --text:      #e8eaf0;
      --muted:     #8b8fa8;
      --radius:    1rem;
    }}

    html, body {{
      margin: 0; padding: 0;
      min-height: 100vh;
      background: var(--bg);
      color: var(--text);
      font-family: 'Inter', ui-sans-serif, system-ui, -apple-system, sans-serif;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
    }}

    /* Radial glow behind card */
    body::before {{
      content: '';
      position: fixed;
      top: 20%;
      left: 50%;
      transform: translateX(-50%);
      width: 600px;
      height: 400px;
      background: radial-gradient(ellipse at center, var(--accent-glow) 0%, transparent 70%);
      pointer-events: none;
    }}

    .card {{
      position: relative;
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 3rem 2.5rem 2.5rem;
      max-width: 42rem;
      width: calc(100% - 2rem);
      text-align: center;
      box-shadow: 0 0 0 1px rgba(92,90,246,0.08), 0 24px 48px rgba(0,0,0,0.4);
    }}

    /* Top accent line */
    .card::before {{
      content: '';
      position: absolute;
      top: 0; left: 2rem; right: 2rem;
      height: 2px;
      background: linear-gradient(90deg, transparent, var(--accent), transparent);
      border-radius: 0 0 2px 2px;
    }}

    .brand {{
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 0.55rem;
      margin-bottom: 2.5rem;
    }}

    .brand img {{
      width: 28px;
      height: 28px;
      border-radius: 6px;
    }}

    .brand-name {{
      font-size: 1rem;
      font-weight: 600;
      letter-spacing: -0.01em;
      color: var(--text);
    }}

    .divider {{
      width: 2rem;
      height: 2px;
      background: var(--accent);
      border-radius: 2px;
      margin: 0 auto 2rem;
      opacity: 0.7;
    }}

    blockquote {{
      margin: 0 0 2rem;
      font-size: clamp(1.25rem, 3.5vw, 1.9rem);
      font-weight: 300;
      line-height: 1.45;
      letter-spacing: -0.02em;
      color: var(--text);
    }}

    blockquote .open-quote {{
      color: var(--accent);
      font-style: normal;
    }}

    .caption {{
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 0.5rem;
      font-size: 0.72rem;
      font-weight: 500;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: var(--muted);
    }}

    .caption .dot {{
      display: inline-block;
      width: 3px;
      height: 3px;
      border-radius: 50%;
      background: var(--accent);
      opacity: 0.6;
    }}

    .refresh-hint {{
      margin-top: 2.5rem;
      font-size: 0.7rem;
      color: var(--muted);
      opacity: 0.5;
      letter-spacing: 0.06em;
    }}

    .refresh-hint a {{
      color: var(--accent);
      text-decoration: none;
      opacity: 0.8;
    }}
    .refresh-hint a:hover {{ opacity: 1; }}

    /* Fade-in animation */
    @keyframes fadeUp {{
      from {{ opacity: 0; transform: translateY(12px); }}
      to   {{ opacity: 1; transform: translateY(0); }}
    }}
    .card {{ animation: fadeUp 0.5s ease both; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="brand">
      <img src="https://askarchie.io/logos/archie-tile-on-dark.png" alt="AskArchie logo">
      <span class="brand-name">AskArchie</span>
    </div>
    <div class="divider"></div>
    <blockquote>
      <span class="open-quote">&ldquo;</span>{quote}&rdquo;
    </blockquote>
    <div class="caption">
      <span class="dot"></span>
      The Agentic Development Platform
      <span class="dot"></span>
    </div>
    <p class="refresh-hint"><a href="">Refresh</a> for another quote</p>
  </div>
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
