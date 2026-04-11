"""
Archie Deployer Agent — deploys infrastructure through the Archie platform.
Browses blueprints, configures deployments, triggers deploys, monitors progress.
"""
import os
import json
import time
import urllib.request
import urllib.error
import boto3
from http.server import HTTPServer, BaseHTTPRequestHandler

MODEL_ID = os.environ.get("MODEL_ID", "us.anthropic.claude-sonnet-4-20250514-v1:0")
ARCHIE_API = os.environ.get("ARCHIE_API", "https://9eumbz9bog.execute-api.us-east-1.amazonaws.com")
ARCHIE_TOKEN = os.environ.get("ARCHIE_TOKEN", "")

SYSTEM_PROMPT = os.environ.get("SYSTEM_PROMPT", """You are Archie Deployer — an AI infrastructure deployer. You can browse blueprints, configure deployments, and deploy infrastructure through the Archie platform.

Your capabilities:
1. List available blueprints and their config fields
2. Get blueprint details (resources, config schema, cost estimate)
3. Deploy a stack from a blueprint with user-provided config
4. Check deployment status and progress
5. List existing stacks to avoid conflicts

IMPORTANT RULES:
- ALWAYS show the user what will be deployed before triggering deploy
- ALWAYS confirm with the user before deploying (ask "Shall I proceed?")
- NEVER deploy without explicit user confirmation
- Show estimated cost and resource count before deploying
- Suggest sensible defaults but let the user override

When deploying:
- Ask for: project name, environment, any template-specific fields
- Show a summary: template, resources, estimated cost, environment
- Wait for confirmation
- Trigger deploy and report the deployment ID
- Poll status until complete or failed""")

bedrock = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION", "us-east-1"))

TOOLS = [
    {
        "name": "list_blueprints",
        "description": "List available infrastructure blueprints in the catalog with their cloud, category, and description.",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "get_blueprint_detail",
        "description": "Get detailed information about a blueprint including config fields, resources, estimated cost, and deployment time.",
        "input_schema": {
            "type": "object",
            "properties": {
                "blueprint_id": {"type": "string", "description": "The action_name or ID of the blueprint (e.g. aws-vpc-nonprod)"}
            },
            "required": ["blueprint_id"]
        }
    },
    {
        "name": "deploy_stack",
        "description": "Deploy a new infrastructure stack from a blueprint. Returns deployment ID for tracking. ONLY call this after user confirms.",
        "input_schema": {
            "type": "object",
            "properties": {
                "template_name": {"type": "string", "description": "Blueprint action_name to deploy (e.g. aws-vpc-nonprod)"},
                "stack_name": {"type": "string", "description": "Name for the new stack (e.g. falcon-vpc-dev)"},
                "config": {"type": "object", "description": "Configuration values: project_name, environment, and template-specific fields"},
            },
            "required": ["template_name", "stack_name", "config"]
        }
    },
    {
        "name": "get_deploy_status",
        "description": "Check the current status of a deployment by its deployment ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "deployment_id": {"type": "string", "description": "The deployment ID (e.g. deploy-1234567890)"}
            },
            "required": ["deployment_id"]
        }
    },
    {
        "name": "list_stacks",
        "description": "List all deployed stacks to check for naming conflicts or see existing infrastructure.",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
]


def call_archie_api(path, method="GET", body=None):
    url = f"{ARCHIE_API}{path}"
    headers = {"Content-Type": "application/json"}
    if ARCHIE_TOKEN:
        headers["Authorization"] = f"Bearer {ARCHIE_TOKEN}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return {"error": f"API {e.code}: {e.read().decode()[:200]}"}
    except Exception as e:
        return {"error": str(e)}


def execute_tool(name, input_data):
    if name == "list_blueprints":
        result = call_archie_api("/marketplace/templates")
        if isinstance(result, list):
            bps = [{"name": b.get("action_name") or b.get("id", ""), "title": b.get("title", ""),
                     "cloud": b.get("cloud", ""), "category": b.get("category", ""),
                     "estimated_cost": b.get("estimated_cost", ""),
                     "description": b.get("description", "")[:100]} for b in result[:30]]
            return {"blueprints": bps, "total": len(result)}
        return result

    elif name == "get_blueprint_detail":
        bp_id = input_data.get("blueprint_id", "")
        result = call_archie_api(f"/marketplace/templates/{bp_id}")
        if isinstance(result, dict) and "error" not in result:
            return {
                "name": result.get("action_name", ""),
                "title": result.get("title", ""),
                "description": result.get("description", ""),
                "cloud": result.get("cloud", ""),
                "estimated_cost": result.get("estimated_cost", ""),
                "deployment_time": result.get("deployment_time", ""),
                "resources": result.get("resources", []),
                "config_fields": result.get("config_fields", []),
            }
        return result

    elif name == "deploy_stack":
        template_name = input_data.get("template_name", "")
        stack_name = input_data.get("stack_name", "")
        config = input_data.get("config", {})
        result = call_archie_api("/stacks/deploy", method="POST", body={
            "template_name": template_name,
            "stack_name": stack_name,
            "config": {"parameters": config},
        })
        return result

    elif name == "get_deploy_status":
        dep_id = input_data.get("deployment_id", "")
        result = call_archie_api(f"/stacks/{dep_id}")
        if isinstance(result, dict) and "error" not in result:
            return {
                "deployment_id": result.get("deploymentId", ""),
                "stack_name": result.get("stack_name", ""),
                "status": result.get("status", ""),
                "resource_count": result.get("resource_count", 0),
                "template": result.get("template_name", ""),
            }
        return result

    elif name == "list_stacks":
        result = call_archie_api("/stacks")
        if isinstance(result, list):
            stacks = [{"id": s.get("deploymentId", ""), "name": s.get("display_name") or s.get("stack_name", ""),
                        "template": s.get("template_name", ""), "status": s.get("status", ""),
                        "cloud": s.get("cloud", "aws"), "environment": s.get("environment", "dev")}
                       for s in result[:20]]
            return {"stacks": stacks, "total": len(result)}
        return result

    return {"error": f"Unknown tool: {name}"}


def agent_conversation(user_message):
    messages = [{"role": "user", "content": user_message}]
    for _ in range(8):
        response = bedrock.invoke_model(
            modelId=MODEL_ID,
            body=json.dumps({"anthropic_version": "bedrock-2023-05-31", "max_tokens": 2048,
                              "system": SYSTEM_PROMPT, "messages": messages, "tools": TOOLS}),
            contentType="application/json",
        )
        result = json.loads(response["body"].read())
        content = result.get("content", [])
        if result.get("stop_reason") == "tool_use":
            tool_results = []
            assistant_content = []
            for block in content:
                assistant_content.append(block)
                if block.get("type") == "tool_use":
                    tool_result = execute_tool(block["name"], block.get("input", {}))
                    tool_results.append({"type": "tool_result", "tool_use_id": block["id"], "content": json.dumps(tool_result)})
            messages.append({"role": "assistant", "content": assistant_content})
            messages.append({"role": "user", "content": tool_results})
        else:
            return "\n".join(b.get("text", "") for b in content if b.get("type") == "text")
    return "I ran out of tool-use rounds. Please try a simpler question."


class AgentHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0)))) if int(self.headers.get("Content-Length", 0)) else {}
        user_message = body.get("input", body.get("message", body.get("prompt", body.get("query", ""))))
        try:
            reply = agent_conversation(user_message)
        except Exception as e:
            reply = f"Error: {str(e)}"
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"output": reply}).encode())

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"status": "healthy", "agent": "archie-deployer"}).encode())

    def log_message(self, format, *args):
        pass

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    server = HTTPServer(("0.0.0.0", port), AgentHandler)
    print(f"Archie Deployer Agent running on port {port}")
    server.serve_forever()
