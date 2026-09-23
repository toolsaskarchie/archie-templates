"""AskArchie quotes, Lambda form. One zip, three entry points:

  handler.api       API Gateway (REST v1 or HTTP v2 payload) → page / ?format=json / POST submit
  handler.consumer  SQS event source → writes submissions and probes to the DynamoDB store
  handler.schedule  EventBridge schedule → writes the "quote of the hour" to the store

Build: ./build.sh  → dist/askarchie-stack-proof-lambda.zip (no third-party deps; boto3 is in the runtime)
"""
import base64
import json
import os
import random
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "common"))  # local dev only

import app  # noqa: E402
import backends as b  # noqa: E402
from archie_proof import seed_quotes  # noqa: E402


def _lambda_ctx(context):
    return {"name": context.function_name, "version": context.function_version,
            "memory": context.memory_limit_in_mb} if context else None


def api(event, context):
    rc = event.get("requestContext") or {}
    method = rc.get("http", {}).get("method") or event.get("httpMethod") or "GET"
    if event.get("rawQueryString") is not None:
        query = event["rawQueryString"]
    else:
        from urllib.parse import urlencode
        query = urlencode(event.get("queryStringParameters") or {})
    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    body = event.get("body") or ""
    if event.get("isBase64Encoded") and body:
        body = base64.b64decode(body).decode("utf-8", "replace")
    status, h, out = app.handle(method, query, headers, body,
                                {"request_context": rc, "lambda": _lambda_ctx(context)})
    return {"statusCode": status, "headers": h, "body": out}


def consumer(event, context):
    """SQS → store. Reports per-message failures so a bad message is retried, not dropped."""
    store = b.DynamoStore()
    failures = []
    for rec in event.get("Records", []):
        try:
            m = json.loads(rec["body"])
            if m.get("kind") == "probe":
                store.put_marker(f"probe-{m['id']}", {"stored_at": b.now_ms(), "msg_id": rec["messageId"]})
            else:
                store.add_submission(m["text"], "queue", sent_at=m.get("sent_at"), msg_id=rec["messageId"])
            print(json.dumps({"archie_proof": "consumed", "kind": m.get("kind"), "msg_id": rec["messageId"]}))
        except Exception as e:  # noqa: BLE001
            print(json.dumps({"archie_proof": "consume_failed", "msg_id": rec.get("messageId"), "error": str(e)}))
            failures.append({"itemIdentifier": rec["messageId"]})
    return {"batchItemFailures": failures}  # enable ReportBatchItemFailures on the event source mapping


def schedule(event, context):
    """EventBridge → pick the quote of the hour → store (if TABLE_NAME is wired) + a proof log line."""
    scheduled = event.get("source") == "aws.events" and event.get("detail-type") == "Scheduled Event"
    quotes = seed_quotes()
    q = quotes[int(time.time() // 3600) % len(quotes)] if scheduled else random.choice(quotes)
    rule = (event.get("resources") or ["manual-invoke"])[0].split("/")[-1]
    rec = {"text": q["text"], "id": q["id"], "rule": rule, "set_by": event.get("source", "manual"),
           "set_at": event.get("time") or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "set_at_epoch": time.time()}
    wrote = False
    if scheduled and os.environ.get("TABLE_NAME"):
        b.DynamoStore().put_marker("featured", rec)
        wrote = True
    # tools/prove.py schedule looks for this line in CloudWatch Logs; manual invokes never count.
    print(json.dumps({"archie_proof": "scheduled" if scheduled else "manual", "rule": rule,
                      "quote_id": q["id"], "wrote_store": wrote}))
    return rec
