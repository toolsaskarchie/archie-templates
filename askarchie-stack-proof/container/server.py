"""AskArchie quotes, container form (ECS Fargate behind an ALB, or a pod on EKS).

  GET  /                page with quote + stack proof
  GET  /?format=json    proof as JSON; 200 when wired, 503 when broken (smoke tests assert this)
  POST /                submit a quote (direct to store, or through SQS when the stack includes sqs)
  GET  /health|/healthz|/ping  shallow liveness "ok" (keeps the target healthy; the deep check is ?format=json)
"""
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "common"))  # local dev

import app  # noqa: E402

HEALTH_PATHS = ("/health", "/healthz", "/ping")


class Handler(BaseHTTPRequestHandler):
    server_version = "askarchie-stack-proof"

    def _send(self, status, headers, body):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(status)
        for k, v in headers.items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _route(self, method):
        path, _, query = self.path.partition("?")
        if path in HEALTH_PATHS:
            return self._send(200, {"Content-Type": "text/plain"}, "ok")
        n = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(n).decode("utf-8", "replace") if n else ""
        headers = {k.lower(): v for k, v in self.headers.items()}
        self._send(*app.handle(method, query, headers, body, {}))

    def do_GET(self):  # noqa: N802
        self._route("GET")

    def do_POST(self):  # noqa: N802
        self._route("POST")

    def log_message(self, fmt, *args):
        sys.stdout.write("%s - %s\n" % (self.address_string(), fmt % args))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    print(f"askarchie-stack-proof on :{port} · ARCHIE_STACK={os.environ.get('ARCHIE_STACK', '(unset)')}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
