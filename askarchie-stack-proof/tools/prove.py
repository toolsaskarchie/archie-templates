#!/usr/bin/env python3
"""Prove a deployed golden path is a connected stack, not a pile of resources.

Exit 0 = wired, 1 = broken (so it drops straight into a smoke test).

  prove.py url      https://<alb|apigw|svc>/                      scenarios 1, 2, 2+4, 2+5, 6 (reads ?format=json)
  prove.py static   --url https://dxxx.cloudfront.net [--s3-url https://bucket.s3.amazonaws.com]   scenario 3
  prove.py sqs      --queue-url URL --table NAME [--key pk]        scenario 4 (headless: sends real messages)
  prove.py schedule --function NAME [--minutes 90]                 scenario 5
  prove.py eks      --cluster NAME [--kms-key-arn ARN] [--url URL] scenario 6 (control-plane + KMS hop)
  prove.py vpc      --vpc-id vpc-...                               scenario 7
  prove.py kms      --key-id alias/...|arn                          scenario 8
Add --json for machine output. AWS calls use your normal credential chain (never pass keys as args).
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "common"))
from archie_proof import Proof, seed_quotes  # noqa: E402

G, R, D, X = "\033[32m", "\033[31m", "\033[2m", "\033[0m"


def http(url, method="GET", timeout=15):
    req = urllib.request.Request(url, method=method, headers={"User-Agent": "askarchie-prove"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, {k.lower(): v for k, v in r.headers.items()}, r.read()
    except urllib.error.HTTPError as e:
        return e.code, {k.lower(): v for k, v in e.headers.items()}, e.read()


# ------------------------------------------------------------------ scenarios with a page
def p_url(a, proof):
    base = a.target.rstrip("/") + "/"
    status, _, body = http(base + "?format=json", timeout=30)
    try:
        d = json.loads(body)
    except ValueError:
        proof.fail("App answered", f"HTTP {status}, not a proof document: {body[:120]!r}")
        return
    proof.stack = d.get("stack", "?")
    proof.hops.extend(d.get("hops", []))
    if not d.get("hops"):
        proof.fail("App answered", f"HTTP {status} with no hops")


def p_static(a, proof):
    base = a.url.rstrip("/")
    proof.hop("HTTPS on the distribution", lambda: _expect(base.startswith("https://"), "url is not https") or base)

    def edge():
        s, h, body = http(base + "/quotes.json")
        _expect(s == 200, f"quotes.json HTTP {s}")
        _expect("x-amz-cf-pop" in h or "cloudfront" in h.get("via", "").lower(), "no CloudFront headers")
        _expect("amazons3" in h.get("server", "").lower(), f"origin server is {h.get('server')!r}, not S3")
        n = len(json.loads(body))
        return f"edge {h.get('x-amz-cf-pop')} · {h.get('x-cache')} · {n} quotes from S3 · etag {h.get('etag')}"
    proof.hop("Client → CloudFront → S3 origin", edge)

    def page():
        s, _, body = http(base + "/")
        _expect(s == 200 and b"Stack proof" in body, f"index HTTP {s} or not the proof page")
        return "index.html served as the default root object"
    proof.hop("Default root object", page)
    if a.s3_url:
        def locked():
            s, _, _ = http(a.s3_url.rstrip("/") + "/quotes.json")
            _expect(s in (401, 403), f"direct S3 returned HTTP {s}: the bucket is reachable around CloudFront")
            return f"direct S3 read refused (HTTP {s}): only CloudFront can reach the origin"
        proof.hop("S3 locked to CloudFront (OAC)", locked)


# ------------------------------------------------------------------ headless scenarios
def p_sqs(a, proof):
    os.environ["QUEUE_URL"], os.environ["TABLE_NAME"], os.environ["TABLE_KEY"] = a.queue_url, a.table, a.key
    import backends as b
    q, store = b.Queue(), b.DynamoStore()
    proof.hop("Producer → SQS", lambda: f"queue {a.queue_url.rsplit('/', 1)[-1]} accepts messages · "
                                        f"{q.sqs.get_queue_attributes(QueueUrl=a.queue_url, AttributeNames=['ApproximateNumberOfMessages'])['Attributes']}")
    proof.hop("SQS → consumer Lambda → DynamoDB (probe)", lambda: b.queue_round_trip(q, store, timeout_s=30))

    def batch():
        quotes = seed_quotes()[:5]
        for qq in quotes:
            q.send("submission", qq["text"])
        deadline = time.time() + 30
        while time.time() < deadline:
            got = {s["text"] for s in store.recent_submissions(50) if s["source"] == "queue"}
            if all(qq["text"] in got for qq in quotes):
                lat = [s["latency_ms"] for s in store.recent_submissions(5) if s["latency_ms"] is not None]
                return f"{len(quotes)} quotes sent, {len(quotes)} landed in {a.table} · latency {min(lat)}–{max(lat)} ms"
            time.sleep(1)
        raise TimeoutError("not every message reached the table within 30s")
    proof.hop("5 quotes through the pipe", batch)


def p_schedule(a, proof):
    import boto3
    lam, ev, logs = boto3.client("lambda"), boto3.client("events"), boto3.client("logs")
    arn = {}

    def fn():
        arn["v"] = lam.get_function(FunctionName=a.function)["Configuration"]["FunctionArn"]
        return arn["v"]
    if not proof.hop("Lambda exists", fn):
        return

    def rule():
        names = ev.list_rule_names_by_target(TargetArn=arn["v"])["RuleNames"]
        _expect(names, "no EventBridge rule targets this function")
        r = ev.describe_rule(Name=names[0])
        _expect(r["State"] == "ENABLED", f"rule {names[0]} is {r['State']}")
        return f"rule {names[0]} · {r.get('ScheduleExpression')} · ENABLED → {a.function}"
    proof.hop("EventBridge rule → Lambda target", rule)

    def fired():
        ev_ = logs.filter_log_events(logGroupName=f"/aws/lambda/{a.function}",
                                     startTime=int((time.time() - a.minutes * 60) * 1000),
                                     filterPattern='"archie_proof" "scheduled"')["events"]
        _expect(ev_, f"no scheduled invocation logged in the last {a.minutes} min (manual invokes don't count)")
        last = json.loads(ev_[-1]["message"][ev_[-1]["message"].index("{"):])
        return f"{len(ev_)} scheduled runs · last quote {last['quote_id']} · wrote store: {last['wrote_store']}"
    proof.hop("Schedule actually fired (CloudWatch Logs)", fired)


def p_eks(a, proof):
    import boto3
    c = {}

    def cluster():
        c["v"] = boto3.client("eks").describe_cluster(name=a.cluster)["cluster"]
        _expect(c["v"]["status"] == "ACTIVE", f"cluster is {c['v']['status']}")
        vpc = c["v"]["resourcesVpcConfig"]
        return f"{a.cluster} · k8s {c['v']['version']} · {vpc['vpcId']} · {len(vpc['subnetIds'])} subnets"
    if not proof.hop("EKS control plane in the VPC", cluster):
        return

    def kms():
        enc = c["v"].get("encryptionConfig") or []
        keys = [e["provider"]["keyArn"] for e in enc if "secrets" in e.get("resources", [])]
        _expect(keys, "secrets are not envelope-encrypted with KMS")
        if a.kms_key_arn:
            _expect(a.kms_key_arn in keys, f"cluster uses {keys[0]}, not the composed key")
        st = boto3.client("kms").describe_key(KeyId=keys[0])["KeyMetadata"]["KeyState"]
        _expect(st == "Enabled", f"key is {st}")
        return f"secrets encrypted with {keys[0].split('/')[-1]} ({st})"
    proof.hop("KMS key → EKS secrets encryption", kms)
    if a.url:
        p_url(argparse.Namespace(target=a.url), proof)


def p_vpc(a, proof):
    import boto3
    ec2 = boto3.client("ec2")
    s = {}

    def vpc():
        v = ec2.describe_vpcs(VpcIds=[a.vpc_id])["Vpcs"][0]
        s["subnets"] = ec2.describe_subnets(Filters=[{"Name": "vpc-id", "Values": [a.vpc_id]}])["Subnets"]
        s["rts"] = ec2.describe_route_tables(Filters=[{"Name": "vpc-id", "Values": [a.vpc_id]}])["RouteTables"]
        azs = {x["AvailabilityZone"] for x in s["subnets"]}
        _expect(len(azs) >= 2, f"subnets span {len(azs)} AZ")
        return f"{a.vpc_id} {v['CidrBlock']} · {len(s['subnets'])} subnets across {len(azs)} AZs"
    if not proof.hop("VPC + subnets across AZs", vpc):
        return

    main = next((rt for rt in s["rts"] if any(x.get("Main") for x in rt["Associations"])), None)

    def rt_for(sid):
        return next((rt for rt in s["rts"] if any(x.get("SubnetId") == sid for x in rt["Associations"])), main)

    def default_route(rt):
        return next((r for r in (rt or {}).get("Routes", []) if r.get("DestinationCidrBlock") == "0.0.0.0/0"), {})
    pub = [x for x in s["subnets"] if default_route(rt_for(x["SubnetId"])).get("GatewayId", "").startswith("igw-")]
    priv = [x for x in s["subnets"] if x not in pub]

    proof.hop("Public subnets → Internet Gateway", lambda: _expect(pub, "no subnet routes 0.0.0.0/0 to an IGW")
              or f"{len(pub)} public subnets route 0.0.0.0/0 → {default_route(rt_for(pub[0]['SubnetId']))['GatewayId']}")

    def nat():
        _expect(priv, "no private subnets")
        bad = [x["SubnetId"] for x in priv if not default_route(rt_for(x["SubnetId"])).get("NatGatewayId")]
        _expect(not bad, f"private subnets with no NAT egress: {bad}")
        nats = ec2.describe_nat_gateways(Filter=[{"Name": "vpc-id", "Values": [a.vpc_id]}, {"Name": "state", "Values": ["available"]}])["NatGateways"]
        pub_ids = {x["SubnetId"] for x in pub}
        _expect(all(n["SubnetId"] in pub_ids for n in nats), "a NAT gateway sits outside the public subnets")
        return f"{len(priv)} private subnets → {len(nats)} NAT gateway(s) in public subnets"
    proof.hop("Private subnets → NAT → public subnets", nat)


def p_kms(a, proof):
    import boto3
    k = boto3.client("kms")
    m = {}

    def meta():
        m["v"] = k.describe_key(KeyId=a.key_id)["KeyMetadata"]
        _expect(m["v"]["KeyState"] == "Enabled", f"key is {m['v']['KeyState']}")
        rot = k.get_key_rotation_status(KeyId=m["v"]["KeyId"]).get("KeyRotationEnabled")
        return f"{m['v']['KeyId']} · {m['v']['KeySpec']} · rotation {'on' if rot else 'OFF'}"
    if not proof.hop("Key enabled", meta):
        return

    def roundtrip():
        q = seed_quotes()[0]["text"].encode()
        ctx = {"app": "askarchie-stack-proof"}
        blob = k.encrypt(KeyId=m["v"]["Arn"], Plaintext=q, EncryptionContext=ctx)["CiphertextBlob"]
        out = k.decrypt(CiphertextBlob=blob, EncryptionContext=ctx)
        _expect(out["Plaintext"] == q and out["KeyId"] == m["v"]["Arn"], "decrypt did not return the quote")
        return f"quote encrypted ({len(blob)} B ciphertext) and decrypted back by the same key"
    proof.hop("Encrypt → decrypt round trip", roundtrip)


def _expect(cond, msg):
    if not cond:
        raise AssertionError(msg)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    sp = ap.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("url"); s.add_argument("target")
    s = sp.add_parser("static"); s.add_argument("--url", required=True); s.add_argument("--s3-url")
    s = sp.add_parser("sqs"); s.add_argument("--queue-url", required=True); s.add_argument("--table", required=True); s.add_argument("--key", default="pk")
    s = sp.add_parser("schedule"); s.add_argument("--function", required=True); s.add_argument("--minutes", type=int, default=90)
    s = sp.add_parser("eks"); s.add_argument("--cluster", required=True); s.add_argument("--kms-key-arn"); s.add_argument("--url")
    s = sp.add_parser("vpc"); s.add_argument("--vpc-id", required=True)
    s = sp.add_parser("kms"); s.add_argument("--key-id", required=True)
    a = ap.parse_args()

    proof = Proof(a.cmd)
    {"url": p_url, "static": p_static, "sqs": p_sqs, "schedule": p_schedule,
     "eks": p_eks, "vpc": p_vpc, "kms": p_kms}[a.cmd](a, proof)
    d = proof.as_dict()
    if a.json:
        print(json.dumps(d, indent=2))
    else:
        print(f"\nAskArchie stack proof · {d['stack']}\n")
        for h in d["hops"]:
            mark = f"{G}✓{X}" if h["ok"] else f"{R}✗{X}"
            print(f"  {mark} {h['hop']}  {D}{h.get('ms', 0)} ms{X}\n      {D}{h['detail']}{X}")
        print(f"\n  {G + 'WIRED' if proof.wired else R + 'BROKEN at: ' + str(d['broken_at'])}{X}\n")
    sys.exit(0 if proof.wired else 1)


if __name__ == "__main__":
    main()
