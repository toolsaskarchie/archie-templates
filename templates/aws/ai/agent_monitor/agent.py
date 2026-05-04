"""
Archie Analyst — cross-stack impact analysis and dependency tracing.
"What breaks if I destroy this VPC?" / "Show me all dependencies"
"""
import os, json, urllib.request, urllib.error, boto3
from http.server import HTTPServer, BaseHTTPRequestHandler

MODEL_ID = os.environ.get("MODEL_ID", "us.anthropic.claude-sonnet-4-20250514-v1:0")
ARCHIE_API = os.environ.get("ARCHIE_API", "https://9eumbz9bog.execute-api.us-east-1.amazonaws.com")
ARCHIE_TOKEN = os.environ.get("ARCHIE_TOKEN", "")

SYSTEM_PROMPT = os.environ.get("SYSTEM_PROMPT", """You are Archie Analyst — an infrastructure dependency and impact analysis agent.

Your job: trace dependencies between stacks, identify blast radius, and warn about cascading failures.

How you work:
1. List all stacks and their outputs (VPC IDs, subnet IDs, security group IDs, etc.)
2. For each stack, check if its config references resources from other stacks
3. Build a dependency map: which stacks depend on which
4. When asked about impact of destroying/modifying a stack, trace all dependents

Key patterns to trace:
- VPC ID: stacks using the same vpc_id depend on the VPC stack
- Subnet IDs: ALB, EKS, RDS, EC2 stacks reference subnet_ids from VPC
- Security Group IDs: compute stacks reference SG IDs from VPC
- App Group: stacks in the same app_group are related

When reporting:
- Show the dependency tree visually
- Flag CRITICAL dependencies (destroying this breaks N stacks)
- Flag SAFE deletions (no dependents)
- Suggest the correct destroy order if user wants to tear down a group
- Be concise but thorough — missing a dependency means broken infrastructure""")

bedrock = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION", "us-east-1"))

TOOLS = [
    {"name": "list_stacks", "description": "List all deployed stacks with status, cloud, template, app_group, and resource count.",
     "input_schema": {"type": "object", "properties": {}, "required": []}},
    {"name": "get_stack", "description": "Get full stack details including outputs (vpc_id, subnet_ids, sg_ids etc.) and config parameters.",
     "input_schema": {"type": "object", "properties": {"stack_id": {"type": "string", "description": "Deployment ID"}}, "required": ["stack_id"]}},
    {"name": "get_stack_resources", "description": "Get all resources in a stack with their types, names, and IDs.",
     "input_schema": {"type": "object", "properties": {"stack_id": {"type": "string", "description": "Deployment ID"}}, "required": ["stack_id"]}},
    {"name": "list_blueprints", "description": "List blueprints to understand what template types exist and their dependency patterns.",
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
                "environment": s.get("environment",""), "app_group": s.get("config",{}).get("parameters",{}).get("app_group",""),
                "resource_count": s.get("resource_count",0), "drift_status": s.get("drift_status","unknown"),
                "outputs": {k:v for k,v in s.get("outputs",{}).items() if any(x in k for x in ["vpc","subnet","sg","security_group","vnet","resource_group"])}}
                for s in result], "total": len(result)}
        return result
    elif name == "get_stack":
        result = call_api(f"/stacks/{inp.get('stack_id','')}")
        if isinstance(result, dict) and "error" not in result:
            return {"id": result.get("deploymentId",""), "name": result.get("stack_name",""),
                "template": result.get("template_name",""), "status": result.get("status",""),
                "outputs": result.get("outputs",{}), "config": result.get("config",{}).get("parameters",{}),
                "resource_count": result.get("resource_count",0)}
        return result
    elif name == "get_stack_resources":
        return call_api(f"/stacks/{inp.get('stack_id','')}/resources")
    elif name == "list_blueprints":
        result = call_api("/marketplace/templates")
        if isinstance(result, list):
            return {"blueprints": [{"name": b.get("action_name",""), "title": b.get("title",""),
                "cloud": b.get("cloud",""), "category": b.get("category","")} for b in result[:30]], "total": len(result)}
        return result
    return {"error": f"Unknown tool: {name}"}


def agent_conversation(user_message):
    messages = [{"role": "user", "content": user_message}]
    for _ in range(8):
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
        self.wfile.write(json.dumps({"status": "healthy", "agent": "archie-analyst"}).encode())
    def log_message(self, *a): pass

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    HTTPServer(("0.0.0.0", port), H).serve_forever()
