"""Framework-free core shared by the Lambda and container forms.

ARCHIE_STACK declares what this deploy is supposed to be wired to, as '+'-joined parts:
    alb+ecs+rds                    scenario 1
    apigw+lambda+dynamodb          scenario 2
    apigw+lambda+dynamodb+sqs      scenarios 2+4 composed (submissions go through the queue)
    apigw+lambda+dynamodb+schedule scenarios 2+5 composed (quote of the hour)
    eks+configmap                  scenario 6
Every declared part adds hops. A declared part whose wire is missing fails; it is never skipped.
"""
import json
import os
import time
import urllib.parse

from archie_proof import Proof, render, seed_quotes
import backends as b

LABEL = {"alb": "ALB", "ecs": "ECS Fargate", "apigw": "API Gateway", "lambda": "Lambda", "eks": "EKS",
         "rds": "RDS Postgres", "dynamodb": "DynamoDB", "configmap": "ConfigMap",
         "sqs": "SQS + consumer Lambda", "schedule": "EventBridge schedule"}
STORES = ("rds", "dynamodb", "configmap")
FALLBACK = {"id": "none", "text": "No quote. The store did not answer, so this stack is not wired.", "views": None}


def parts():
    raw = os.environ.get("ARCHIE_STACK", "").strip()
    return [p for p in raw.split("+") if p]


def _front_hops(proof, ps, headers, platform):
    if "alb" in ps:
        def alb():
            trace = headers.get("x-amzn-trace-id")
            if not trace or not headers.get("x-forwarded-for"):
                raise RuntimeError("no X-Amzn-Trace-Id / X-Forwarded-For: this request did not come through the ALB")
            return f"client {headers['x-forwarded-for'].split(',')[0]} → ALB → target ({trace.split(';')[0]})"
        proof.hop("Internet → ALB → target", alb)
    if "ecs" in ps:
        proof.hop("ALB target → ECS task", b.ecs_task)
    if "apigw" in ps:
        def apigw():
            rc = platform.get("request_context") or {}
            if not rc.get("apiId"):
                raise RuntimeError("no API Gateway requestContext: Lambda was invoked directly, not through the API")
            return f"API {rc['apiId']} · stage {rc.get('stage')} · {rc.get('routeKey') or rc.get('resourcePath', '')}"
        proof.hop("Internet → API Gateway → Lambda", apigw)
    if "lambda" in ps:
        def lam():
            lc = platform.get("lambda")
            if not lc:
                raise RuntimeError("not running inside Lambda")
            return f"{lc['name']} v{lc['version']} · {lc['memory']} MB · {os.environ.get('AWS_REGION', '?')}"
        proof.hop("Lambda runtime", lam)
    if "eks" in ps:
        def eks():
            if not os.environ.get("KUBERNETES_SERVICE_HOST"):
                raise RuntimeError("not running in a Kubernetes pod (no KUBERNETES_SERVICE_HOST)")
            who = f"pod {os.environ.get('POD_NAME', '?')} on node {os.environ.get('NODE_NAME', '?')}"
            return f"{who} · " + b.k8s_api_read_configmap()
        proof.hop("Service → Pod → Kubernetes API", eks)


def build(headers, platform, want_submissions=True):
    ps = parts()
    proof = Proof("+".join(ps) or "(none)")
    if not ps:
        proof.fail("Declared stack", "ARCHIE_STACK is not set, so there is nothing to prove")
        return proof, None, FALLBACK, None, []
    unknown = [p for p in ps if p not in LABEL]
    if unknown:
        proof.fail("Declared stack", f"unknown parts: {unknown}")

    _front_hops(proof, ps, headers, platform)
    front = "Pod" if "eks" in ps else "ECS task" if "ecs" in ps else "Lambda"

    store, quote, featured, subs = None, FALLBACK, None, []
    kind = next((p for p in ps if p in STORES), None)
    if kind is None:
        proof.fail("Store", "declared stack has no data store (rds, dynamodb or configmap)")
    else:
        holder = {}
        cls = {"rds": b.PostgresStore, "dynamodb": b.DynamoStore, "configmap": b.ConfigMapStore}[kind]

        def connect():
            holder["s"] = cls()
            return holder["s"].describe()
        if proof.hop(f"{front} → {LABEL[kind]}", connect):
            store = holder["s"]
            if kind == "rds":
                proof.hop("RDS connection encrypted", store.tls)

            def read():
                holder["q"] = store.random_quote(seed_quotes())
                return (f"read quote {holder['q']['id']}" +
                        (f", wrote views={holder['q']['views']}" if holder["q"]["views"] is not None else ""))
            if proof.hop(f"{LABEL[kind]} read" + ("" if kind == "configmap" else "/write"), read):
                quote = holder["q"]

    if "sqs" in ps:
        if kind != "dynamodb" or store is None:
            proof.fail("Queue → consumer → store", "needs a working dynamodb store (the consumer writes there)")
        else:
            proof.hop("Queue → consumer Lambda → store", lambda: b.queue_round_trip(b.Queue(), store))

    if "schedule" in ps:
        if store is None or kind == "configmap":
            proof.fail("Schedule → Lambda → store", "needs a writable store")
        else:
            max_age = int(os.environ.get("ARCHIE_SCHEDULE_MAX_AGE_S", "3900"))

            def sched():
                f = store.get_marker("featured")
                if not f:
                    raise RuntimeError("no scheduled quote yet: the rule has not fired or the target is not wired")
                age = time.time() - f["set_at_epoch"]
                if age > max_age:
                    raise RuntimeError(f"last scheduled write was {int(age)}s ago (> {max_age}s): the schedule stopped")
                holder["f"] = f
                return f"rule {f['rule']} fired {int(age)}s ago and wrote the quote of the hour"
            if proof.hop("EventBridge → Lambda → store", sched):
                featured = holder["f"]

    if want_submissions and store is not None and kind != "configmap":
        try:
            subs = store.recent_submissions(5)
        except Exception:  # noqa: BLE001 - display only
            subs = []
    return proof, store, quote, featured, subs


def title():
    ps = parts()
    return " · ".join(LABEL.get(p, p) for p in ps) or "undeclared stack"


def handle(method, query, headers, body, platform):
    """Returns (status, headers, body). headers must be lower-cased."""
    q = urllib.parse.parse_qs(query or "")
    flash = None
    ps = parts()
    can_submit = any(p in ps for p in ("rds", "dynamodb"))

    if method == "POST" and can_submit:
        text = (urllib.parse.parse_qs(body or "").get("text") or [""])[0].strip()
        if text:
            try:
                if "sqs" in ps:
                    _, mid = b.Queue().send("submission", text)
                    flash = f"Queued as message {mid[:8]}. The consumer Lambda writes it to the store."
                else:
                    store = b.PostgresStore() if "rds" in ps else b.DynamoStore()
                    store.add_submission(text, "direct")
                    flash = "Written straight to the store."
            except Exception as e:  # noqa: BLE001
                flash = f"Submission failed: {type(e).__name__}: {e}"
        # PRG: redirect back to the same URL so refresh doesn't resubmit
        return 303, {"Location": "?" + urllib.parse.urlencode({"flash": flash or ""}), "Cache-Control": "no-store"}, ""

    proof, _, quote, featured, subs = build(headers, platform)
    if (q.get("format") or [""])[0] == "json":
        d = proof.as_dict()
        d["quote"] = quote
        return (200 if proof.wired else 503), {"Content-Type": "application/json", "Cache-Control": "no-store"}, json.dumps(d, indent=2)
    page = render(title(), quote, proof, featured=featured, submissions=subs, can_submit=can_submit,
                  submit_via="queue" if "sqs" in ps else "direct", flash=(q.get("flash") or [None])[0])
    return 200, {"Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store"}, page
