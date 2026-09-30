"""AskArchie quotes page.

Returns a different quote on every request, counts the visits it has served,
and lets a visitor add a quote of their own.

WHERE THE STATE LIVES IS NOT THIS FILE'S DECISION. Left alone, the counter and
the submissions are module-level: they belong to ONE running instance and start
again when it restarts, scales out or is redeployed. That is the honest shape of
a page nobody has given anywhere to keep things.

Give it somewhere and it keeps them there:

    QUOTES_TABLE   a DynamoDB table — its name, or better its ARN (the region
                   is read from the ARN). Any key schema: the page reads the
                   table's own keys and writes two items, the counter and the
                   list of submissions. It needs dynamodb:DescribeTable,
                   GetItem and UpdateItem on that table, nothing else.

If the table cannot be reached the page still renders and says so, rather than
pretending it kept what it did not.
"""

import html
import json
import os
import random
import sys
import threading
import zlib

# ONE LOCK, because a threaded server answers several requests at once and a
# read-modify-write on a counter is the textbook place that goes wrong.
_LOCK = threading.Lock()

# What this instance holds when nothing durable has been given to it. `views` is
# what Marketing asked to see; `submitted` is what visitors have added, newest
# first, capped so a page left open overnight cannot grow without bound.
STATE = {"views": 0, "submitted": []}

MAX_SUBMITTED = 25
MAX_QUOTE_CHARS = 140

# Set when the durable store failed on the last request, so the page can say
# "not kept" instead of showing an in-memory number as if it were the real one.
KEPT = {"ok": True}


class _Table:
    """The durable store, when QUOTES_TABLE names one. Two items, any key schema.

    The table's own key names are read once (DescribeTable) rather than assumed:
    whoever built the table chose them, and a page that insists on `pk`/`sk`
    breaks the first time somebody else designs the table. A range key, if the
    table has one, gets a fixed value so each item is still one item.
    """

    def __init__(self, ref: str):
        import boto3  # only when a table is configured; the local run needs nothing
        name, region = ref, None
        if ref.startswith("arn:"):
            parts = ref.split(":")
            region, name = parts[3], parts[5].split("/", 1)[1]
        region = (region or os.environ.get("AWS_REGION")
                  or os.environ.get("AWS_DEFAULT_REGION") or "us-east-1")
        self._ddb = boto3.client("dynamodb", region_name=region)
        self._name = name
        schema = self._ddb.describe_table(TableName=name)["Table"]
        types = {a["AttributeName"]: a["AttributeType"]
                 for a in schema.get("AttributeDefinitions") or []}
        self._keys = [(k["AttributeName"], types.get(k["AttributeName"], "S"), k["KeyType"])
                      for k in schema["KeySchema"]]

    def _key(self, what: str) -> dict:
        out = {}
        for name, typ, kind in self._keys:
            if typ == "N":
                value = str(zlib.crc32(what.encode())) if kind == "HASH" else "0"
            else:
                value = what if kind == "HASH" else "0"
            out[name] = {typ: value}
        return out

    def count_visit(self) -> int:
        r = self._ddb.update_item(
            TableName=self._name, Key=self._key("quotes#views"),
            UpdateExpression="ADD #v :one",
            ExpressionAttributeNames={"#v": "views"},
            ExpressionAttributeValues={":one": {"N": "1"}},
            ReturnValues="UPDATED_NEW")
        return int(r["Attributes"]["views"]["N"])

    def add(self, text: str) -> None:
        r = self._ddb.update_item(
            TableName=self._name, Key=self._key("quotes#submitted"),
            UpdateExpression="SET #q = list_append(:new, if_not_exists(#q, :empty))",
            ExpressionAttributeNames={"#q": "quotes"},
            ExpressionAttributeValues={":new": {"L": [{"S": text}]}, ":empty": {"L": []}},
            ReturnValues="UPDATED_NEW")
        n = len(r["Attributes"]["quotes"]["L"])
        if n > MAX_SUBMITTED:
            # Trimmed after the append rather than inside it: DynamoDB cannot
            # slice a list in an update, and a list a few items over the cap
            # between two requests is harmless.
            self._ddb.update_item(
                TableName=self._name, Key=self._key("quotes#submitted"),
                UpdateExpression="REMOVE " + ", ".join(
                    f"#q[{i}]" for i in range(MAX_SUBMITTED, n)),
                ExpressionAttributeNames={"#q": "quotes"})

    def submitted(self) -> list:
        r = self._ddb.get_item(TableName=self._name, Key=self._key("quotes#submitted"),
                               ConsistentRead=True)
        return [x["S"] for x in ((r.get("Item") or {}).get("quotes") or {}).get("L", [])]


_STORE = {"table": None, "tried": False}


def _table():
    """The configured table, or None. Built once; a table that could not be
    opened is retried on the next request rather than forgotten for good."""
    ref = os.environ.get("QUOTES_TABLE", "").strip()
    if not ref:
        return None
    if _STORE["table"] is None:
        try:
            _STORE["table"] = _Table(ref)
        except Exception as e:  # noqa: BLE001 — the page still renders
            print(f"[quotes] store unavailable: {type(e).__name__}: {e}", file=sys.stderr)
            return None
    return _STORE["table"]


def _durably(fn, fallback):
    t = _table()
    if t is not None:
        try:
            out = fn(t)
            KEPT["ok"] = True
            return out
        except Exception as e:  # noqa: BLE001
            print(f"[quotes] store call failed: {type(e).__name__}: {e}", file=sys.stderr)
    KEPT["ok"] = not os.environ.get("QUOTES_TABLE", "").strip()
    return fallback()


def record_visit() -> int:
    """Count this visit and return the running total."""
    def _here():
        with _LOCK:
            STATE["views"] += 1
            return STATE["views"]
    return _durably(lambda t: t.count_visit(), _here)


def add_quote(text: str) -> bool:
    """Take a visitor's quote. False when there was nothing usable in it.

    Trimmed and length-capped before it is stored, and escaped where it is
    rendered — a public box that puts submitted text on a public page is the
    one place in this app where a stranger writes the HTML.
    """
    cleaned = " ".join(str(text or "").split())[:MAX_QUOTE_CHARS].strip()
    if not cleaned:
        return False

    def _here():
        with _LOCK:
            STATE["submitted"].insert(0, cleaned)
            del STATE["submitted"][MAX_SUBMITTED:]
    _durably(lambda t: t.add(cleaned), _here)
    return True


def submitted_quotes() -> list:
    """What visitors have sent, newest first."""
    def _here():
        with _LOCK:
            return list(STATE["submitted"])
    return _durably(lambda t: t.submitted(), _here)


def all_quotes():
    """What the page can show: the visitors' first, then the originals."""
    return submitted_quotes() + QUOTES

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


def _page(quote: str, views: int = 0, submitted=None) -> str:
    # ESCAPED HERE, because the quote on display is no longer always ours.
    # Visitor submissions join the rotation, so the blockquote interpolates a
    # stranger's text into the page's own HTML — the recent-list was escaped
    # from the start and this one was not, which is the half-fix that reads as
    # safe. Caught by feeding it an <img onerror> before this shipped.
    quote = html.escape(str(quote or ""))
    submitted = list(submitted or [])
    # THE LABEL SAYS WHOSE NUMBER IT IS. Without a store it is one instance's,
    # and saying "views" alone would let a restart look like lost traffic.
    if not os.environ.get("QUOTES_TABLE", "").strip():
        count_label = "views served by this instance"
    elif KEPT["ok"]:
        count_label = "views so far"
    else:
        count_label = "views on this instance &mdash; not being kept right now"
    recent = "".join(
        f'<li>{html.escape(q)}</li>' for q in submitted[:5])
    recent_block = (
        f'<div class="recent"><div class="recent-k">Added by visitors</div>'
        f'<ul>{recent}</ul></div>' if recent else "")
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
    .counter {{
      display: flex; align-items: baseline; gap: .5rem;
      justify-content: center; margin-top: .25rem;
    }}
    .count {{
      font-size: 1.5rem; font-weight: 600; color: var(--accent);
      font-variant-numeric: tabular-nums;
    }}
    .count-label {{ font-size: .8rem; color: var(--muted); }}
    .add {{ display: flex; gap: .5rem; margin-top: 1.25rem; }}
    .add input {{
      flex: 1; padding: .6rem .8rem; border-radius: .6rem;
      border: 1px solid var(--border); background: var(--bg);
      color: var(--text); font: inherit; font-size: .9rem;
    }}
    .add input:focus-visible {{ outline: 2px solid var(--accent); outline-offset: 1px; }}
    .add button {{
      padding: .6rem 1rem; border-radius: .6rem; border: 0; cursor: pointer;
      background: var(--accent); color: #fff; font: inherit; font-weight: 500;
    }}
    .recent {{ margin-top: 1.25rem; text-align: left; }}
    .recent-k {{
      font-size: .7rem; letter-spacing: .08em; text-transform: uppercase;
      color: var(--muted); margin-bottom: .4rem;
    }}
    .recent ul {{ margin: 0; padding-left: 1.1rem; }}
    .recent li {{ font-size: .85rem; color: var(--muted); margin: .2rem 0; }}
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
    <div class="counter">
      <span class="count">{views:,}</span>
      <span class="count-label">{count_label}</span>
    </div>
    <form class="add" method="POST" action="">
      <input name="quote" maxlength="{MAX_QUOTE_CHARS}" autocomplete="off"
             placeholder="Add a quote of your own&hellip;" aria-label="Your quote">
      <button type="submit">Add</button>
    </form>
    {recent_block}
    <p class="refresh-hint"><a href="">Refresh</a> for another quote</p>
  </div>
</body>
</html>"""


def _method(event) -> str:
    """The verb, whichever envelope this arrived in.

    A Lambda function URL and API Gateway v2 put it under `requestContext.http`;
    the v1 REST shape uses `httpMethod`. Reading only one of them is how a form
    post silently renders the page again instead of saving anything.
    """
    ctx = (event or {}).get("requestContext") or {}
    return str((ctx.get("http") or {}).get("method")
               or (event or {}).get("httpMethod") or "GET").upper()


def _submitted_quote(event) -> str:
    """The `quote` field out of a form post, base64 or not, form or JSON."""
    import base64
    from urllib.parse import parse_qs
    body = (event or {}).get("body") or ""
    if (event or {}).get("isBase64Encoded"):
        try:
            body = base64.b64decode(body).decode("utf-8", "replace")
        except Exception:  # noqa: BLE001 — an unreadable body is simply no quote
            return ""
    body = str(body)
    if body.lstrip().startswith("{"):
        try:
            return str((json.loads(body) or {}).get("quote") or "")
        except ValueError:
            return ""
    return (parse_qs(body).get("quote") or [""])[0]


def handler(event, context):
    if _method(event) == "POST":
        add_quote(_submitted_quote(event))
        # POST-REDIRECT-GET, so a refresh after adding does not add it twice.
        return {"statusCode": 303,
                "headers": {"Location": "", "Cache-Control": "no-store"},
                "body": ""}
    views = record_visit()
    submitted = submitted_quotes()
    quote = random.choice(submitted + QUOTES)
    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "text/html; charset=utf-8",
            # no-store so each refresh re-invokes and shows a fresh quote
            "Cache-Control": "no-store",
        },
        "body": _page(quote, views, submitted),
    }
