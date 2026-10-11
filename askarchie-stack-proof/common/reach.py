"""Reachability hops: can THIS process open a connection to each wired endpoint?

Run from inside the consumer (the Lambda, the task, the pod), so the answer
exercises everything that decides it on the real network: the security groups
on both ends, the subnets and their routes, NAT or endpoints for egress, DNS.
A hop is DNS resolve + TCP connect. Nothing is sent over the connection, so a
database is never logged into and a queue is never written to — the question is
only whether the wire is open.

The hop list comes from Archie (env ARCHIE_REACH, or an `archie_reach` invoke
event): a JSON list of {name, host, port, kind}. `kind` is tcp or https; both
are a TCP connect, https defaulting the port to 443.
"""
import json
import os
import socket
import time

TIMEOUT_S = 3.0


def hops_from_env():
    raw = os.environ.get("ARCHIE_REACH", "").strip()
    if not raw:
        return []
    try:
        got = json.loads(raw)
    except ValueError:
        return [{"name": "ARCHIE_REACH", "error": "not valid JSON"}]
    return got if isinstance(got, list) else []


def probe(hop, timeout=TIMEOUT_S):
    """One hop: {name, host, port, ok, ms, error?}. Never raises."""
    name = str(hop.get("name") or "")
    host = str(hop.get("host") or "").strip()
    kind = str(hop.get("kind") or "tcp")
    try:
        port = int(hop.get("port") or (443 if kind == "https" else 0))
    except (TypeError, ValueError):
        port = 0
    out = {"name": name, "host": host, "port": port, "kind": kind, "ok": False, "ms": 0}
    if hop.get("error"):
        out["error"] = str(hop["error"])
        return out
    if not host or not port:
        out["error"] = "no host or port to reach"
        return out
    t = time.perf_counter()
    try:
        addrs = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as e:
        out["error"] = f"DNS: {e}"
        return out
    last = "no address"
    for fam, styp, proto, _, sa in addrs:
        s = socket.socket(fam, styp, proto)
        s.settimeout(timeout)
        try:
            s.connect(sa)
            out["ok"] = True
            out["ms"] = round((time.perf_counter() - t) * 1000, 1)
            out["address"] = sa[0]
            return out
        except socket.timeout:
            last = "timeout"
        except OSError as e:
            last = "refused" if getattr(e, "errno", None) in (61, 111) else f"{type(e).__name__}: {e}"
        finally:
            s.close()
    out["error"] = last
    out["ms"] = round((time.perf_counter() - t) * 1000, 1)
    return out


def probe_all(hops, timeout=TIMEOUT_S):
    return [probe(h, timeout) for h in hops or [] if isinstance(h, dict)]


def add_to_proof(proof, hops=None):
    """Add one Proof hop per reach hop (named `reach: <name>`)."""
    for r in probe_all(hops if hops is not None else hops_from_env()):
        label = f"reach: {r['name'] or r['host']} ({r['host']}:{r['port']})"
        if r["ok"]:
            proof.hops.append({"hop": label, "ok": True, "ms": r["ms"],
                               "detail": f"connected to {r.get('address', r['host'])}:{r['port']}"})
        else:
            proof.fail(label, r.get("error") or "unreachable")
