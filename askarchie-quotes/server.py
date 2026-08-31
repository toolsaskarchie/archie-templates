"""The same quote page, over plain HTTP, for anything that is not a Lambda.

`handler.py` answers a Lambda event. A container behind a load balancer answers
a socket, and a target group health-checks it — so the app needs both shapes to
serve both demos. Rather than a second copy of the page (which would drift the
moment somebody edits one), this imports `QUOTES` and `_page` from the handler
and is the only file that knows about sockets.

No dependencies, deliberately: `requirements.txt` is empty and stays that way,
so the image builds from `python:3.12-slim` with nothing fetched at build time.

    python3 server.py          # then open http://localhost:8080
"""

import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from handler import QUOTES, _page

import random

PORT = int(os.environ.get("PORT", "8080"))

# A LOAD BALANCER ASKS BEFORE IT SENDS ANYONE. A target group health-checks a
# path and drains the target when it fails, so a container that only serves
# `/` comes up, never passes, and the URL 502s with every resource present and
# healthy-looking in the console.
HEALTH_PATHS = ("/health", "/healthz", "/ping")


class Quotes(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self):  # noqa: N802 — BaseHTTPRequestHandler's spelling
        path = self.path.split("?", 1)[0]
        if path in HEALTH_PATHS:
            self._send(b"ok", "text/plain; charset=utf-8")
            return
        self._send(_page(random.choice(QUOTES)).encode("utf-8"),
                   "text/html; charset=utf-8")

    def _send(self, body: bytes, content_type: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        # Same reason as the Lambda: each refresh must re-render, or the quote
        # never changes and the one interactive thing on the page is dead.
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        # One line per request, on stdout, so it lands in the task logs.
        print(f"{self.address_string()} {fmt % args}", flush=True)


if __name__ == "__main__":
    print(f"askarchie-quotes listening on :{PORT}", flush=True)
    ThreadingHTTPServer(("", PORT), Quotes).serve_forever()
