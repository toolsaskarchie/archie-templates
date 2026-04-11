"""
Archie Monitor Agent — read-only infrastructure visibility.
Lists stacks, checks drift status, views stack details, browses blueprints.
"""
import os
import json
import urllib.request
import urllib.error
import boto3
from http.server import HTTPServer, BaseHTTPRequestHandler

MODEL_ID = os.environ.get("MODEL_ID", "us.anthropic.claude-sonnet-4-20250514-v1:0")
ARCHIE_API = os.environ.get("ARCHIE_API", "https://9eumbz9bog.execute-api.us-east-1.amazonaws.com")
ARCHIE_TOKEN = os.environ.get("ARCHIE_TOKEN", "")

SYSTEM_PROMPT = os.environ.get("SYSTEM_PROMPT", """You are Archie Monitor — an AI infrastructure observer. You have read-only access to the Archie platform.

Your capabilities:
1. List all deployed infrastructure stacks with status, cloud, and health
2. Get detailed information about any specific stack
3. Check drift status — find what changed from expected state
4. Trigger drift detection on stacks
5. Browse available blueprints in the catalog

When reporting:
- Lead with a summary (N stacks, N healthy, N drifted)
- Flag any drift as urgent with details
- Show stack names in bold, include cloud provider and environment
- Be concise and proactive — if you see issues, flag them

You are READ-ONLY. You cannot deploy, destroy, or remediate. If asked to take action, explain what needs to happen and suggest the user ask Archie Deployer or Archie Remediator.""")

bedrock = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION", "us-east-1"))

TOOLS = [
    {
        "name": "list_stacks",
        "description": "List all deployed infrastructure stacks with their status, cloud provider, environment, and template name.",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "get_stack",
        "description": "Get detailed information about a specific stack including resources, outputs, and configuration.",
        "input_schema": {
            "type": "object",
            "properties": {
                "stack_id": {"type": "string", "description": "The deployment ID of the stack (e.g. deploy-1234567890)"}
            },
            "required": ["stack_id"]
        }
    },
    {
        "name": "check_drift",
        "description": "Trigger a drift detection check on a stack to see if cloud resources have changed from their expected state.",
        "input_schema": {
            "type": "object",
            "properties": {
                "stack_id": {"type": "string", "description": "The deployment ID of the stack to check"}
            },
            "required": ["stack_id"]
        }
    },
    {
        "name": "get_drift",
        "description": "Get the current drift status for a stack — shows which resources have drifted from their expected configuration.",
        "input_schema": {
            "type": "object",
            "properties": {
                "stack_id": {"type": "string", "description": "The deployment ID of the stack"}
            },
            "required": ["stack_id"]
        }
    },
    {
        "name": "list_blueprints",
        "description": "List available infrastructure blueprints in the catalog that can be deployed.",
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
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return {"error": f"API {e.code}: {e.read().decode()[:200]}"}
    except Exception as e:
        return {"error": str(e)}


def execute_tool(name, input_data):
    if name == "list_stacks":
        result = call_archie_api("/stacks")
        if isinstance(result, list):
            stacks = [{"id": s.get("deploymentId", ""), "name": s.get("display_name") or s.get("stack_name", ""),
                        "template": s.get("template_name", ""), "status": s.get("status", ""),
                        "cloud": s.get("cloud", "aws"), "environment": s.get("environment", "dev"),
                        "resource_count": s.get("resource_count", 0), "drift_status": s.get("drift_status", "unknown")}
                       for s in result[:20]]
            return {"stacks": stacks, "total": len(result)}
        return result
    elif name == "get_stack":
        return call_archie_api(f"/stacks/{input_data.get('stack_id', '')}")
    elif name == "check_drift":
        return call_archie_api(f"/stacks/{input_data.get('stack_id', '')}/drift/check", method="POST")
    elif name == "get_drift":
        return call_archie_api(f"/stacks/{input_data.get('stack_id', '')}/drift")
    elif name == "list_blueprints":
        result = call_archie_api("/marketplace/templates")
        if isinstance(result, list):
            bps = [{"name": b.get("action_name") or b.get("id", ""), "title": b.get("title", ""),
                     "cloud": b.get("cloud", ""), "category": b.get("category", ""),
                     "description": b.get("description", "")[:100]} for b in result[:20]]
            return {"blueprints": bps, "total": len(result)}
        return result
    return {"error": f"Unknown tool: {name}"}


def agent_conversation(user_message):
    messages = [{"role": "user", "content": user_message}]
    for _ in range(5):
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
        self.wfile.write(json.dumps({"status": "healthy", "agent": "archie-monitor"}).encode())

    def log_message(self, format, *args):
        pass

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    server = HTTPServer(("0.0.0.0", port), AgentHandler)
    print(f"Archie Monitor Agent running on port {port}")
    server.serve_forever()
