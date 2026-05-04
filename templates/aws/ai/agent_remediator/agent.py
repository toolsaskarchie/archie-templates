"""
Archie Auditor — compliance scanning and security reporting.
"Are all my stacks SOC2 compliant?" / "Generate a security report"
"""
import os, json, urllib.request, urllib.error, boto3
from http.server import HTTPServer, BaseHTTPRequestHandler

MODEL_ID = os.environ.get("MODEL_ID", "us.anthropic.claude-sonnet-4-20250514-v1:0")
ARCHIE_API = os.environ.get("ARCHIE_API", "https://9eumbz9bog.execute-api.us-east-1.amazonaws.com")
ARCHIE_TOKEN = os.environ.get("ARCHIE_TOKEN", "")

SYSTEM_PROMPT = os.environ.get("SYSTEM_PROMPT", """You are Archie Auditor — a compliance and security assessment agent.

Your job: scan all infrastructure for security gaps, compliance violations, and best-practice deviations. Generate reports that an auditor or CISO would find useful.

What you check:
- Encryption at rest (S3, RDS, EBS, DynamoDB)
- Encryption in transit (HTTPS listeners, TLS)
- Public access (S3 buckets, security groups with 0.0.0.0/0)
- IAM least privilege (wildcard actions, overly broad resources)
- Logging enabled (VPC flow logs, CloudTrail, access logs)
- Drift status (unmanaged changes = compliance risk)
- Tagging compliance (required tags: Team, Environment, ManagedBy)
- Network segmentation (private subnets for databases, no direct internet)

How you report:
- Start with an executive summary: N stacks, N compliant, N issues
- Group findings by severity: CRITICAL / WARNING / INFO
- For each finding: stack name, resource, what's wrong, how to fix
- End with a compliance score (percentage of checks passing)
- Format as a structured report suitable for SOC2/ISO27001 evidence

You are READ-ONLY. You assess and report — you don't fix. Recommend remediation steps.""")

bedrock = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION", "us-east-1"))

TOOLS = [
    {"name": "list_stacks", "description": "List all deployed stacks with status, cloud, template, and drift status.",
     "input_schema": {"type": "object", "properties": {}, "required": []}},
    {"name": "get_stack", "description": "Get full stack details including outputs, config parameters, and template info.",
     "input_schema": {"type": "object", "properties": {"stack_id": {"type": "string"}}, "required": ["stack_id"]}},
    {"name": "get_stack_resources", "description": "Get all resources in a stack with types and properties for compliance checking.",
     "input_schema": {"type": "object", "properties": {"stack_id": {"type": "string"}}, "required": ["stack_id"]}},
    {"name": "get_drift", "description": "Get drift status — unmanaged changes are a compliance risk.",
     "input_schema": {"type": "object", "properties": {"stack_id": {"type": "string"}}, "required": ["stack_id"]}},
    {"name": "compliance_check", "description": "Run Archie's built-in compliance engine (23 rules across AWS/Azure/GCP) against a template's source code.",
     "input_schema": {"type": "object", "properties": {"template_name": {"type": "string", "description": "Template action_name to scan"}}, "required": ["template_name"]}},
    {"name": "list_blueprints", "description": "List blueprints to check governance config (locked fields, required fields).",
     "input_schema": {"type": "object", "properties": {}, "required": []}},
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
                "resource_count": s.get("resource_count",0)} for s in result], "total": len(result)}
        return result
    elif name == "get_stack":
        return call_api(f"/stacks/{inp.get('stack_id','')}")
    elif name == "get_stack_resources":
        return call_api(f"/stacks/{inp.get('stack_id','')}/resources")
    elif name == "get_drift":
        result = call_api(f"/stacks/{inp.get('stack_id','')}/drift")
        if isinstance(result, dict) and "error" not in result:
            return {"drift_status": result.get("driftStatus","unknown"), "drifted_count": len(result.get("driftedResources",[])),
                "drifted_resources": [{"name": r.get("name",""), "type": r.get("type",""), "changes": r.get("changes",[])}
                    for r in result.get("driftedResources",[])[:10]]}
        return result
    elif name == "compliance_check":
        return call_api("/stacks/compliance-check", method="POST", body={"template_name": inp.get("template_name","")})
    elif name == "list_blueprints":
        result = call_api("/marketplace/templates")
        if isinstance(result, list):
            return {"blueprints": [{"name": b.get("action_name",""), "title": b.get("title",""),
                "cloud": b.get("cloud",""), "category": b.get("category","")} for b in result[:30]], "total": len(result)}
        return result
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
        self.wfile.write(json.dumps({"status": "healthy", "agent": "archie-auditor"}).encode())
    def log_message(self, *a): pass

if __name__ == "__main__":
    HTTPServer(("0.0.0.0", int(os.environ.get("PORT", "8080"))), H).serve_forever()
