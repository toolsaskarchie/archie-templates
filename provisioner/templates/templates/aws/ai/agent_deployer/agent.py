"""
Archie Planner — multi-stack deployment orchestration.
"Set up project falcon with VPC, database, and ALB in staging"
"""
import os, json, urllib.request, urllib.error, boto3
from http.server import HTTPServer, BaseHTTPRequestHandler

MODEL_ID = os.environ.get("MODEL_ID", "us.anthropic.claude-sonnet-4-20250514-v1:0")
ARCHIE_API = os.environ.get("ARCHIE_API", "https://9eumbz9bog.execute-api.us-east-1.amazonaws.com")
ARCHIE_TOKEN = os.environ.get("ARCHIE_TOKEN", "")

SYSTEM_PROMPT = os.environ.get("SYSTEM_PROMPT", """You are Archie Planner — a multi-stack deployment planning agent.

Your job: help users plan and execute multi-stack deployments. When someone says "set up project falcon", you figure out what blueprints they need, in what order, with what config.

How you work:
1. Understand what the user wants to build (web app? API? data pipeline?)
2. Browse available blueprints to find the right templates
3. Plan the deployment order (VPC first → then DB → then compute → then ALB)
4. Check existing stacks for naming conflicts and reusable infrastructure
5. Present the plan with estimated cost and resource count
6. Deploy each stack in order (with user confirmation at each step)

Key rules:
- ALWAYS present the full plan before deploying anything
- Show: stack name, template, environment, estimated cost, dependency chain
- Use consistent naming: {project}-{service}-{env} (e.g. falcon-vpc-dev, falcon-rds-dev)
- Use app_group to tie related stacks together
- Check for existing VPCs/VNets before creating new ones (brownfield)
- NEVER deploy without user confirmation
- If a deployment fails, stop and report — don't continue the chain""")

bedrock = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION", "us-east-1"))

TOOLS = [
    {"name": "list_blueprints", "description": "List all available blueprints with cloud, category, cost estimate, and resource count.",
     "input_schema": {"type": "object", "properties": {}, "required": []}},
    {"name": "get_blueprint_detail", "description": "Get blueprint details: config fields, resources, estimated cost, deployment time.",
     "input_schema": {"type": "object", "properties": {"blueprint_id": {"type": "string"}}, "required": ["blueprint_id"]}},
    {"name": "list_stacks", "description": "List existing stacks to check for conflicts and reusable infrastructure (existing VPCs etc.).",
     "input_schema": {"type": "object", "properties": {}, "required": []}},
    {"name": "get_stack", "description": "Get stack details including outputs (VPC IDs, subnet IDs) for brownfield deployments.",
     "input_schema": {"type": "object", "properties": {"stack_id": {"type": "string"}}, "required": ["stack_id"]}},
    {"name": "deploy_stack", "description": "Deploy a stack from a blueprint. ONLY after user confirms the plan. Returns deployment ID.",
     "input_schema": {"type": "object", "properties": {
         "template_name": {"type": "string", "description": "Blueprint action_name"},
         "stack_name": {"type": "string", "description": "Stack name (e.g. falcon-vpc-dev)"},
         "config": {"type": "object", "description": "Config values: project_name, environment, app_group, and template-specific fields"}
     }, "required": ["template_name", "stack_name", "config"]}},
    {"name": "get_deploy_status", "description": "Check deployment status by ID. Poll until COMPLETED or FAILED.",
     "input_schema": {"type": "object", "properties": {"deployment_id": {"type": "string"}}, "required": ["deployment_id"]}},
]


def call_api(path, method="GET", body=None):
    url = f"{ARCHIE_API}{path}"
    headers = {"Content-Type": "application/json"}
    if ARCHIE_TOKEN: headers["Authorization"] = f"Bearer {ARCHIE_TOKEN}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp: return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e: return {"error": f"API {e.code}: {e.read().decode()[:200]}"}
    except Exception as e: return {"error": str(e)}


def execute_tool(name, inp):
    if name == "list_blueprints":
        result = call_api("/marketplace/templates")
        if isinstance(result, list):
            return {"blueprints": [{"name": b.get("action_name",""), "title": b.get("title",""),
                "cloud": b.get("cloud",""), "category": b.get("category",""),
                "estimated_cost": b.get("estimated_cost",""), "description": b.get("description","")[:80]}
                for b in result[:30]], "total": len(result)}
        return result
    elif name == "get_blueprint_detail":
        result = call_api(f"/marketplace/templates/{inp.get('blueprint_id','')}")
        if isinstance(result, dict) and "error" not in result:
            return {"name": result.get("action_name",""), "title": result.get("title",""),
                "estimated_cost": result.get("estimated_cost",""), "deployment_time": result.get("deployment_time",""),
                "resources": result.get("resources",[]), "config_fields": result.get("config_fields",[])}
        return result
    elif name == "list_stacks":
        result = call_api("/stacks")
        if isinstance(result, list):
            return {"stacks": [{"id": s.get("deploymentId",""), "name": s.get("display_name") or s.get("stack_name",""),
                "template": s.get("template_name",""), "status": s.get("status",""), "cloud": s.get("cloud","aws"),
                "environment": s.get("environment",""), "app_group": s.get("config",{}).get("parameters",{}).get("app_group","")}
                for s in result], "total": len(result)}
        return result
    elif name == "get_stack":
        result = call_api(f"/stacks/{inp.get('stack_id','')}")
        if isinstance(result, dict) and "error" not in result:
            return {"id": result.get("deploymentId",""), "name": result.get("stack_name",""),
                "outputs": result.get("outputs",{}), "config": result.get("config",{}).get("parameters",{})}
        return result
    elif name == "deploy_stack":
        return call_api("/stacks/deploy", method="POST", body={
            "template_name": inp.get("template_name",""), "stack_name": inp.get("stack_name",""),
            "config": {"parameters": inp.get("config",{})}})
    elif name == "get_deploy_status":
        result = call_api(f"/stacks/{inp.get('deployment_id','')}")
        if isinstance(result, dict) and "error" not in result:
            return {"deployment_id": result.get("deploymentId",""), "status": result.get("status",""),
                "resource_count": result.get("resource_count",0)}
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
        self.wfile.write(json.dumps({"status": "healthy", "agent": "archie-planner"}).encode())
    def log_message(self, *a): pass

if __name__ == "__main__":
    HTTPServer(("0.0.0.0", int(os.environ.get("PORT", "8080"))), H).serve_forever()
