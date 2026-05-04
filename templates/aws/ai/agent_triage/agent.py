"""
Archie Triage — incident investigation and cross-stack correlation.
"Something's wrong with production" / "Why is my ALB unhealthy?"
"""
import os, json, urllib.request, urllib.error, boto3
from http.server import HTTPServer, BaseHTTPRequestHandler

MODEL_ID = os.environ.get("MODEL_ID", "us.anthropic.claude-sonnet-4-20250514-v1:0")
ARCHIE_API = os.environ.get("ARCHIE_API", "https://9eumbz9bog.execute-api.us-east-1.amazonaws.com")
ARCHIE_TOKEN = os.environ.get("ARCHIE_TOKEN", "")

SYSTEM_PROMPT = os.environ.get("SYSTEM_PROMPT", """You are Archie Triage — an incident investigation agent. When something breaks, you investigate across all stacks and find the root cause.

How you investigate:
1. Check ALL stacks for failed/degraded status
2. Check ALL stacks for drift (unmanaged changes often cause incidents)
3. Correlate: did drift in stack A break stack B? (e.g. VPC SG change → ALB health check fail)
4. Check recent deployments — did a recent deploy cause the issue?
5. Build a timeline: what changed, when, in what order

Your investigation pattern:
- Start broad: list all stacks, scan for any failures or drift
- Narrow down: focus on affected stacks and their dependencies
- Correlate: trace which change likely caused the issue
- Report: root cause, affected resources, recommended fix

When reporting:
- Lead with the root cause (or most likely cause)
- Show the chain of events: "VPC security group drifted → ALB lost connectivity → health checks failing"
- Classify severity: P1 (production down), P2 (degraded), P3 (warning)
- Suggest specific fix steps
- Flag any stacks that need immediate attention

You are investigative — think like an SRE. Don't just list facts, connect the dots.""")

bedrock = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION", "us-east-1"))

TOOLS = [
    {"name": "list_stacks", "description": "List all stacks with status, drift status, cloud, and resource count. First step in any investigation.",
     "input_schema": {"type": "object", "properties": {}, "required": []}},
    {"name": "get_stack", "description": "Get full stack details: status, outputs, config, recent changes.",
     "input_schema": {"type": "object", "properties": {"stack_id": {"type": "string"}}, "required": ["stack_id"]}},
    {"name": "get_stack_resources", "description": "Get all resources in a stack — check for failed or missing resources.",
     "input_schema": {"type": "object", "properties": {"stack_id": {"type": "string"}}, "required": ["stack_id"]}},
    {"name": "get_drift", "description": "Get drift details: which resources changed, what fields, expected vs actual. Drift is the #1 cause of incidents.",
     "input_schema": {"type": "object", "properties": {"stack_id": {"type": "string"}}, "required": ["stack_id"]}},
    {"name": "check_drift", "description": "Trigger a fresh drift check on a stack. Use when drift status is 'unknown' or stale.",
     "input_schema": {"type": "object", "properties": {"stack_id": {"type": "string"}}, "required": ["stack_id"]}},
]


def call_api(path, method="GET", body=None):
    url = f"{ARCHIE_API}{path}"
    headers = {"Content-Type": "application/json"}
    if ARCHIE_TOKEN: headers["Authorization"] = f"Bearer {ARCHIE_TOKEN}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp: return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e: return {"error": f"API {e.code}: {e.read().decode()[:200]}"}
    except Exception as e: return {"error": str(e)}


def execute_tool(name, inp):
    if name == "list_stacks":
        result = call_api("/stacks")
        if isinstance(result, list):
            return {"stacks": [{"id": s.get("deploymentId",""), "name": s.get("display_name") or s.get("stack_name",""),
                "template": s.get("template_name",""), "status": s.get("status",""), "cloud": s.get("cloud","aws"),
                "environment": s.get("environment",""), "drift_status": s.get("drift_status","unknown"),
                "drifted_count": s.get("drifted_count",0), "resource_count": s.get("resource_count",0),
                "created_at": s.get("created_at","")} for s in result], "total": len(result)}
        return result
    elif name == "get_stack":
        return call_api(f"/stacks/{inp.get('stack_id','')}")
    elif name == "get_stack_resources":
        return call_api(f"/stacks/{inp.get('stack_id','')}/resources")
    elif name == "get_drift":
        result = call_api(f"/stacks/{inp.get('stack_id','')}/drift")
        if isinstance(result, dict) and "error" not in result:
            return {"drift_status": result.get("driftStatus","unknown"),
                "drifted_count": len(result.get("driftedResources",[])),
                "drifted_resources": [{"name": r.get("name",""), "type": r.get("type",""),
                    "status": r.get("status",""), "changes": r.get("changes",[])}
                    for r in result.get("driftedResources",[])[:10]]}
        return result
    elif name == "check_drift":
        return call_api(f"/stacks/{inp.get('stack_id','')}/drift/check", method="POST")
    return {"error": f"Unknown tool: {name}"}


def agent_conversation(user_message):
    messages = [{"role": "user", "content": user_message}]
    for _ in range(10):
        response = bedrock.invoke_model(modelId=MODEL_ID, contentType="application/json",
            body=json.dumps({"anthropic_version": "bedrock-2023-05-31", "max_tokens": 4096,
                "system": SYSTEM_PROMPT, "messages": messages, "tools": TOOLS}))
        result = json.loads(response["body"].read())
        content = result.get("content", [])
        if result.get("stop_reason") == "tool_use":
            tool_results, assistant_content = [], []
            for block in content:
                assistant_content.append(block)
                if block.get("type") == "tool_use":
                    tool_results.append({"type": "tool_result", "tool_use_id": block["id"],
                        "content": json.dumps(execute_tool(block["name"], block.get("input", {})))})
            messages.append({"role": "assistant", "content": assistant_content})
            messages.append({"role": "user", "content": tool_results})
        else:
            return "\n".join(b.get("text", "") for b in content if b.get("type") == "text")
    return "Max tool rounds reached."


class H(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0) or 0))) if int(self.headers.get("Content-Length", 0) or 0) else {}
        msg = body.get("input", body.get("message", body.get("prompt", "")))
        try: reply = agent_conversation(msg)
        except Exception as e: reply = f"Error: {e}"
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
        self.wfile.write(json.dumps({"output": reply}).encode())
    def do_GET(self):
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
        self.wfile.write(json.dumps({"status": "healthy", "agent": "archie-triage"}).encode())
    def log_message(self, *a): pass

if __name__ == "__main__":
    HTTPServer(("0.0.0.0", int(os.environ.get("PORT", "8080"))), H).serve_forever()
