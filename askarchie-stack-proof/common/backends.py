"""Stores and wires. Each one talks to the real resource; nothing is mocked in prod code.

Store interface (Postgres, DynamoDB, ConfigMap):
    describe()                 -> str   the hop detail (proves who answered)
    random_quote(seed)         -> dict  {id, text, views}; seeds lazily from quotes.json
    add_submission(text, source, sent_at=None, msg_id=None)
    recent_submissions(n)      -> list
    put_marker(key, dict) / get_marker(key) -> dict | None   (probes, featured quote)
"""
import json
import os
import random
import ssl
import time
import urllib.request
import uuid


def now_ms():
    return int(time.time() * 1000)


# --------------------------------------------------------------------------- Postgres (RDS)
class PostgresStore:
    """Env: DB_HOST, DB_PORT(5432), DB_NAME, DB_USER, DB_PASSWORD.
    On ECS, DB_PASSWORD should be injected by the task definition from Secrets Manager
    (`secrets: valueFrom`), so a successful login also proves the secret wiring."""

    CA = os.environ.get("RDS_CA_BUNDLE", "/app/rds-ca.pem")

    def __init__(self):
        import pg8000.native  # only the container image ships this
        ctx = ssl.create_default_context()
        if os.path.exists(self.CA):
            ctx.load_verify_locations(self.CA)
            self.tls_mode = "verified against RDS CA"
        else:
            ctx.check_hostname, ctx.verify_mode = False, ssl.CERT_NONE
            self.tls_mode = "encrypted, cert not verified (no RDS CA bundle)"
        self.db = pg8000.native.Connection(
            user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"],
            host=os.environ["DB_HOST"], port=int(os.environ.get("DB_PORT", "5432")),
            database=os.environ.get("DB_NAME", "postgres"), ssl_context=ctx, timeout=5)
        for ddl in (
            "CREATE TABLE IF NOT EXISTS archie_quotes (id text PRIMARY KEY, text text NOT NULL, views int NOT NULL DEFAULT 0)",
            "CREATE TABLE IF NOT EXISTS archie_submissions (id serial PRIMARY KEY, text text NOT NULL, source text, "
            "sent_at bigint, stored_at bigint, msg_id text)",
            "CREATE TABLE IF NOT EXISTS archie_markers (k text PRIMARY KEY, v text NOT NULL)",
        ):
            self.db.run(ddl)

    def describe(self):
        addr, db, ver = self.db.run("SELECT host(inet_server_addr()), current_database(), current_setting('server_version')")[0]
        return f"postgres {ver} at {addr} · db {db} · logged in as {os.environ['DB_USER']}"

    def tls(self):
        on = self.db.run("SELECT ssl, version FROM pg_stat_ssl WHERE pid = pg_backend_pid()")[0]
        if not on[0]:
            raise RuntimeError("connection is NOT encrypted")
        return f"{on[1]} · {self.tls_mode}"

    def random_quote(self, seed):
        q = random.choice(seed)
        self.db.run("INSERT INTO archie_quotes (id, text) VALUES (:i, :t) ON CONFLICT (id) DO NOTHING", i=q["id"], t=q["text"])
        text, views = self.db.run("UPDATE archie_quotes SET views = views + 1 WHERE id = :i RETURNING text, views", i=q["id"])[0]
        return {"id": q["id"], "text": text, "views": views}

    def add_submission(self, text, source, sent_at=None, msg_id=None):
        self.db.run("INSERT INTO archie_submissions (text, source, sent_at, stored_at, msg_id) VALUES (:t,:s,:a,:b,:m)",
                    t=text[:200], s=source, a=sent_at, b=now_ms(), m=msg_id)

    def recent_submissions(self, n=5):
        rows = self.db.run("SELECT text, source, sent_at, stored_at FROM archie_submissions ORDER BY id DESC LIMIT :n", n=n)
        return [{"text": r[0], "source": r[1], "latency_ms": (r[3] - r[2]) if r[2] else None} for r in rows]

    def put_marker(self, k, v):
        self.db.run("INSERT INTO archie_markers (k, v) VALUES (:k,:v) ON CONFLICT (k) DO UPDATE SET v = EXCLUDED.v", k=k, v=json.dumps(v))

    def get_marker(self, k):
        r = self.db.run("SELECT v FROM archie_markers WHERE k = :k", k=k)
        return json.loads(r[0][0]) if r else None


# --------------------------------------------------------------------------- DynamoDB
class DynamoStore:
    """Env: TABLE_NAME, TABLE_KEY (partition key attribute name, string type, default 'pk').
    Single-table: quote#<id>, sub#<ts>#<uuid>, marker#<name>."""

    def __init__(self):
        import boto3
        self.name = os.environ["TABLE_NAME"]
        self.key = os.environ.get("TABLE_KEY", "pk")
        self.client = boto3.client("dynamodb")
        self.t = boto3.resource("dynamodb").Table(self.name)

    def describe(self):
        try:
            d = self.client.describe_table(TableName=self.name)["Table"]
            sse = d.get("SSEDescription")
            enc = (f"KMS {sse.get('KMSMasterKeyArn', '').split('/')[-1]}" if sse and sse.get("Status") == "ENABLED"
                   else "AWS-owned key (default)")
            return f"table {self.name} · {d['TableStatus']} · encryption: {enc}"
        except Exception as e:
            code = getattr(e, "response", {}).get("Error", {}).get("Code", "")
            if code != "AccessDeniedException":  # a missing table IS a wiring failure
                raise
            # DescribeTable not granted is not a wiring failure; the read/write hop still has to pass
            return f"table {self.name} · encryption: unknown (no dynamodb:DescribeTable)"

    def random_quote(self, seed):
        q = random.choice(seed)
        k = {self.key: f"quote#{q['id']}"}
        r = self.t.update_item(Key=k, UpdateExpression="SET #t = if_not_exists(#t, :t) ADD #v :one",
                               ExpressionAttributeNames={"#t": "text", "#v": "views"},
                               ExpressionAttributeValues={":t": q["text"], ":one": 1}, ReturnValues="ALL_NEW")["Attributes"]
        return {"id": q["id"], "text": r["text"], "views": int(r["views"])}

    def add_submission(self, text, source, sent_at=None, msg_id=None):
        stored = now_ms()
        item = {self.key: f"sub#{stored:015d}#{uuid.uuid4().hex[:8]}", "text": text[:200], "source": source, "stored_at": stored}
        if sent_at:
            item["sent_at"] = int(sent_at)
        if msg_id:
            item["msg_id"] = msg_id
        self.t.put_item(Item=item)

    def recent_submissions(self, n=5):
        items, kw = [], {"FilterExpression": "begins_with(#k, :p)", "ExpressionAttributeNames": {"#k": self.key},
                         "ExpressionAttributeValues": {":p": "sub#"}}
        while True:  # demo-sized table; a scan is fine
            r = self.t.scan(**kw)
            items += r["Items"]
            if "LastEvaluatedKey" not in r:
                break
            kw["ExclusiveStartKey"] = r["LastEvaluatedKey"]
        items.sort(key=lambda i: i[self.key], reverse=True)
        return [{"text": i["text"], "source": i.get("source"),
                 "latency_ms": int(i["stored_at"]) - int(i["sent_at"]) if "sent_at" in i else None} for i in items[:n]]

    def put_marker(self, k, v):
        self.t.put_item(Item={self.key: f"marker#{k}", "v": json.dumps(v)})

    def get_marker(self, k):
        i = self.t.get_item(Key={self.key: f"marker#{k}"}, ConsistentRead=True).get("Item")
        return json.loads(i["v"]) if i else None


# --------------------------------------------------------------------------- ConfigMap (EKS)
class ConfigMapStore:
    """Env: QUOTES_FILE (default /etc/archie/quotes.json), mounted from the archie-quotes ConfigMap.
    Read-only: no views counter, no submissions. The image does NOT fall back to its own copy."""

    def __init__(self):
        self.path = os.environ.get("QUOTES_FILE", "/etc/archie/quotes.json")
        with open(self.path, encoding="utf-8") as f:
            self.quotes = json.load(f)

    def describe(self):
        return f"{len(self.quotes)} quotes read from mounted {self.path}"

    def random_quote(self, seed):
        q = random.choice(self.quotes)
        return {"id": q["id"], "text": q["text"], "views": None}


# --------------------------------------------------------------------------- SQS
class Queue:
    """Env: QUEUE_URL."""

    def __init__(self):
        import boto3
        self.url = os.environ["QUEUE_URL"]
        self.sqs = boto3.client("sqs")

    def send(self, kind, text, ident=None):
        body = {"kind": kind, "id": ident or uuid.uuid4().hex, "text": text[:200], "sent_at": now_ms()}
        mid = self.sqs.send_message(QueueUrl=self.url, MessageBody=json.dumps(body))["MessageId"]
        return body, mid


def queue_round_trip(queue, store, timeout_s=10.0):
    """Send a probe through SQS and wait for the consumer Lambda to write it to the store."""
    body, mid = queue.send("probe", "round-trip probe")
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        m = store.get_marker(f"probe-{body['id']}")
        if m:
            return f"probe {mid[:8]} sent → consumer Lambda → store in {m['stored_at'] - body['sent_at']} ms"
        time.sleep(0.4)
    raise TimeoutError(f"probe {mid[:8]} was queued but never reached the store in {timeout_s:.0f}s "
                       "(consumer not subscribed, no table permission, or wrong TABLE_NAME)")


# --------------------------------------------------------------------------- Platform identity
def ecs_task():
    uri = os.environ.get("ECS_CONTAINER_METADATA_URI_V4")
    if not uri:
        raise RuntimeError("no ECS task metadata endpoint: not running as an ECS task")
    with urllib.request.urlopen(f"{uri}/task", timeout=2) as r:
        t = json.load(r)
    return f"task {t['TaskARN'].split('/')[-1][:12]} · {t.get('LaunchType', '?')} · {t.get('AvailabilityZone', '?')} · cluster {t['Cluster'].split('/')[-1]}"


def k8s_api_read_configmap(name="archie-quotes"):
    """Pod → API server with its service account token. Proves the SA + RBAC Role wiring."""
    sa = "/var/run/secrets/kubernetes.io/serviceaccount"
    host, port = os.environ["KUBERNETES_SERVICE_HOST"], os.environ.get("KUBERNETES_SERVICE_PORT", "443")
    ns = open(f"{sa}/namespace").read().strip()
    token = open(f"{sa}/token").read().strip()
    ctx = ssl.create_default_context(cafile=f"{sa}/ca.crt")
    req = urllib.request.Request(f"https://{host}:{port}/api/v1/namespaces/{ns}/configmaps/{name}",
                                 headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, context=ctx, timeout=3) as r:
        cm = json.load(r)
    return f"service account read configmap {ns}/{name} (resourceVersion {cm['metadata']['resourceVersion']})"
