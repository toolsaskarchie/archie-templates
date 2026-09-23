"""Stack proof primitives + the page.

A hop is a real call across a wire (HTTP, SQL, AWS API, K8s API, file mount).
A hop never passes because an env var exists. It passes only if the call
behind it succeeds. The verdict is "wired" only when every hop the declared
stack needs has passed.
"""
import html
import json
import os
import time

HERE = os.path.dirname(os.path.abspath(__file__))


def seed_quotes():
    with open(os.path.join(HERE, "quotes.json"), encoding="utf-8") as f:
        return json.load(f)


class Proof:
    def __init__(self, stack):
        self.stack = stack
        self.hops = []

    def hop(self, name, fn):
        """Run fn(); its return value is the detail string. Exceptions fail the hop."""
        t = time.perf_counter()
        try:
            detail, ok = fn(), True
        except Exception as e:  # noqa: BLE001 - every failure is a broken hop
            detail, ok = f"{type(e).__name__}: {e}", False
        self.hops.append({
            "hop": name, "ok": ok, "detail": str(detail),
            "ms": round((time.perf_counter() - t) * 1000, 1),
        })
        return ok

    def fail(self, name, detail):
        self.hops.append({"hop": name, "ok": False, "detail": detail, "ms": 0})

    @property
    def wired(self):
        return bool(self.hops) and all(h["ok"] for h in self.hops)

    def as_dict(self):
        broken = next((h["hop"] for h in self.hops if not h["ok"]), None)
        return {"stack": self.stack, "verdict": "wired" if self.wired else "broken",
                "broken_at": broken, "hops": self.hops}


def _e(s):
    return html.escape(str(s), quote=True)


def render(title, quote, proof, featured=None, submissions=None,
           can_submit=False, submit_via=None, flash=None):
    d = proof.as_dict()
    ok = d["verdict"] == "wired"
    rows = "".join(
        f'<li class="{"ok" if h["ok"] else "bad"}"><span class="dot">{"✓" if h["ok"] else "✗"}</span>'
        f'<div><div class="hop">{_e(h["hop"])} <span class="ms">{h["ms"]} ms</span></div>'
        f'<div class="detail">{_e(h["detail"])}</div></div></li>'
        for h in d["hops"])
    badge = ("WIRED: every hop answered" if ok
             else f'BROKEN at: {_e(d["broken_at"])}')
    feat = ""
    if featured:
        feat = (f'<div class="featured"><div class="label">Quote of the hour · set by EventBridge '
                f'{_e(featured.get("set_at", ""))}</div>{_e(featured.get("text", ""))}</div>')
    form = ""
    if can_submit:
        via = "through the queue, then the consumer Lambda, then the store" if submit_via == "queue" else "straight into the store"
        form = (f'<form method="post" action=""><label>Add a quote. It goes {via}.</label>'
                f'<div class="row"><input name="text" maxlength="200" required '
                f'placeholder="Archie, but make it a quote…"><button>Send</button></div></form>')
    subs = ""
    if submissions:
        items = "".join(
            f'<li>{_e(s["text"])}<span class="meta">{_e(s.get("source", ""))}'
            f'{" · " + _e(s["latency_ms"]) + " ms queue→store" if s.get("latency_ms") is not None else ""}'
            f'</span></li>' for s in submissions)
        subs = f'<div class="subs"><div class="label">Recent submissions (read back from the store)</div><ul>{items}</ul></div>'
    fl = f'<div class="flash">{_e(flash)}</div>' if flash else ""
    views = f'<div class="views">Served {quote["views"]} time{"" if quote["views"] == 1 else "s"} (counter lives in the store, not the app)</div>' if quote.get("views") is not None else ""
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AskArchie Stack Proof</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&display=swap" rel="stylesheet">
<style>
*,*::before,*::after{{box-sizing:border-box}}
:root{{--bg:#0b0d18;--surface:#12152a;--border:#1e2340;--accent:#5c5af6;--glow:rgba(92,90,246,.25);
--text:#e8eaf0;--muted:#8b8fa8;--ok:#34d399;--bad:#f87171}}
html,body{{margin:0;min-height:100vh;background:var(--bg);color:var(--text);
font-family:Inter,ui-sans-serif,system-ui,sans-serif;display:flex;justify-content:center;align-items:flex-start}}
body::before{{content:'';position:fixed;top:10%;left:50%;transform:translateX(-50%);width:600px;max-width:100vw;height:400px;
background:radial-gradient(ellipse at center,var(--glow) 0%,transparent 70%);pointer-events:none}}
.card{{position:relative;background:var(--surface);border:1px solid var(--border);border-radius:1rem;
padding:2.5rem 2rem 2rem;max-width:44rem;width:calc(100% - 2rem);margin:2rem 0;
box-shadow:0 0 0 1px rgba(92,90,246,.08),0 24px 48px rgba(0,0,0,.4)}}
.card::before{{content:'';position:absolute;top:0;left:2rem;right:2rem;height:2px;
background:linear-gradient(90deg,transparent,var(--accent),transparent)}}
.brand{{display:flex;align-items:center;justify-content:center;gap:.55rem;margin-bottom:.4rem;font-weight:600}}
.brand img{{width:28px;height:28px;border-radius:6px}}
.stack{{text-align:center;color:var(--muted);font-size:.85rem;margin-bottom:2rem}}
blockquote{{margin:0 0 .6rem;font-size:1.45rem;font-weight:300;line-height:1.45;text-align:center}}
.views{{text-align:center;color:var(--muted);font-size:.8rem;margin-bottom:1.5rem}}
.featured{{border:1px dashed var(--border);border-radius:.7rem;padding:.8rem 1rem;margin:0 0 1.5rem;font-size:1rem}}
.label{{color:var(--muted);font-size:.72rem;letter-spacing:.06em;text-transform:uppercase;margin-bottom:.35rem}}
.badge{{display:block;text-align:center;font-weight:600;letter-spacing:.04em;padding:.6rem;border-radius:.6rem;margin:1rem 0 .8rem;
background:{"rgba(52,211,153,.12)" if ok else "rgba(248,113,113,.12)"};color:{"var(--ok)" if ok else "var(--bad)"}}}
ul.hops{{list-style:none;margin:0;padding:0}}
ul.hops li{{display:flex;gap:.7rem;padding:.55rem 0;border-top:1px solid var(--border)}}
.dot{{font-weight:700;width:1.1rem}} li.ok .dot{{color:var(--ok)}} li.bad .dot{{color:var(--bad)}}
.hop{{font-weight:500;font-size:.92rem}} .ms{{color:var(--muted);font-weight:400;font-size:.75rem}}
.detail{{color:var(--muted);font-size:.8rem;word-break:break-word}}
form{{margin-top:1.6rem}} form label{{display:block;color:var(--muted);font-size:.85rem;margin-bottom:.45rem}}
.row{{display:flex;gap:.5rem}} input{{flex:1;min-width:0;background:var(--bg);border:1px solid var(--border);color:var(--text);
border-radius:.5rem;padding:.6rem .75rem;font:inherit}}
button{{background:var(--accent);color:#fff;border:0;border-radius:.5rem;padding:.6rem 1rem;font:inherit;font-weight:500;cursor:pointer}}
.subs{{margin-top:1.4rem}} .subs ul{{margin:0;padding-left:1.1rem}} .subs li{{margin:.3rem 0;font-size:.9rem}}
.meta{{color:var(--muted);font-size:.75rem;margin-left:.4rem}}
.flash{{background:rgba(92,90,246,.12);border-radius:.5rem;padding:.55rem .8rem;font-size:.85rem;margin-bottom:1rem}}
footer{{text-align:center;color:var(--muted);font-size:.75rem;margin-top:1.6rem}} a{{color:var(--accent)}}
</style></head><body><main class="card">
<div class="brand"><img src="https://askarchie.io/logos/archie-tile-on-dark.png" alt="">AskArchie</div>
<div class="stack">{_e(title)}</div>
{fl}{feat}
<blockquote>{_e(quote["text"]) if quote["id"] == "none" else "“" + _e(quote["text"]) + "”"}</blockquote>{views}
<div class="label">Stack proof</div>
<span class="badge">{badge}</span>
<ul class="hops">{rows}</ul>
{form}{subs}
<footer>The Agentic Development Platform · <a href="">refresh</a> · <a href="?format=json">proof.json</a></footer>
</main></body></html>"""
