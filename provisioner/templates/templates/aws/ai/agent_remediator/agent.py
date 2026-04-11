"""
Archie Remediator Agent — fixes configuration drift in infrastructure.
Checks drift, shows diffs, previews remediation, applies fixes.
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

SYSTEM_PROMPT = os.environ.get("SYSTEM_PROMPT", """You are Archie Remediator — an AI infrastructure fixer. You detect and fix configuration drift in cloud infrastructure.

Your capabilities:
1. List stacks and their drift status
2. Trigger drift detection on specific stacks
3. Get detailed drift information (what changed, expected vs actual)
4. Preview remediation (dry-run showing what will be fixed)
5. Apply remediation to restore desired state

IMPORTANT RULES:
- ALWAYS check drift status before remediating
- ALWAYS preview remediation before applying
- ALWAYS explain what drifted and why it matters (security impact)
- ALWAYS confirm with the user before applying remediation
- Classify drift severity: CRITICAL (security groups, IAM, encryption), WARNING (config changes), INFO (tags)

When remediating:
- Show the drift summary: N resources drifted, severity breakdown
- For each drifted resource: show field name, expected value, actual value
- Preview the fix: what will change back
- Wait for user confirmation
- Apply and report result""")

bedrock = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION", "us-east-1"))

TOOLS = [
    {
        "name": "list_stacks",
        "description": "List all deployed stacks with their drift status (in_sync, drifted, unknown).",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "check_drift",
        "description": "Trigger a fresh drift detection check on a stack. Returns immediately — drift results available via get_drift after a few seconds.",
        "input_schema": {
            "type": "object",
            "properties": {
                "stack_id": {"type": "string", "description": "The deployment ID of the stack"}
            },
            "required": ["stack_id"]
        }
    },
    {
        "name": "get_drift",
        "description": "Get detailed drift information for a stack: which resources drifted, which fields changed, expected vs actual values.",
        "input_schema": {
            "type": "object",
            "properties": {
                "stack_id": {"type": "string", "description": "The deployment ID of the stack"}
            },
            "required": ["stack_id"]
        }
    },
    {
        "name": "preview_remediation",
        "description": "Preview what remediation will do — dry-run showing which resources will be restored to desired state. Does NOT apply changes.",
        "input_schema": {
            "type": "object",
            "properties": {
                "stack_id": {"type": "string", "description": "The deployment ID of the stack to remediate"}
            },
            "required": ["stack_id"]
        }
    },
    {
        "name": "apply_remediation",
        "description": "Apply remediation to restore drifted resources to their desired state. ONLY call after user confirms. This makes real changes to cloud resources.",
        "input_schema": {
            "type": "object",
            "properties": {
                "stack_id": {"type": "string", "description": "The deployment ID of the stack to remediate"}
            },
            "required": ["stack_id"]
        }
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
    if name == "list_stacks":
        result = call_archie_api("/stacks")
        if isinstance(result, list):
            stacks = [{"id": s.get("deploymentId", ""), "name": s.get("display_name") or s.get("stack_name", ""),
                        "template": s.get("template_name", ""), "status": s.get("status", ""),
                        "cloud": s.get("cloud", "aws"), "drift_status": s.get("drift_status", "unknown"),
                        "drifted_count": s.get("drifted_count", 0)}
                       for s in result[:20]]
            return {"stacks": stacks, "total": len(result)}
        return result

    elif name == "check_drift":
        stack_id = input_data.get("stack_id", "")
        return call_archie_api(f"/stacks/{stack_id}/drift/check", method="POST")

    elif name == "get_drift":
        stack_id = input_data.get("stack_id", "")
        result = call_archie_api(f"/stacks/{stack_id}/drift")
        if isinstance(result, dict) and "error" not in result:
            drifted = result.get("driftedResources", [])
            return {
                "drift_status": result.get("driftStatus", "unknown"),
                "drifted_count": len(drifted),
                "drifted_resources": [{
                    "name": r.get("name", ""),
                    "type": r.get("type", ""),
                    "status": r.get("status", ""),
                    "changes": r.get("changes", [])[:5],
                } for r in drifted[:10]],
            }
        return result

    elif name == "preview_remediation":
        stack_id = input_data.get("stack_id", "")
        return call_archie_api(f"/stacks/{stack_id}/drift/remediate", method="POST", body={"mode": "preview"})

    elif name == "apply_remediation":
        stack_id = input_data.get("stack_id", "")
        return call_archie_api(f"/stacks/{stack_id}/drift/remediate", method="POST", body={"mode": "apply"})

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
        self.wfile.write(json.dumps({"status": "healthy", "agent": "archie-remediator"}).encode())

    def log_message(self, format, *args):
        pass

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    server = HTTPServer(("0.0.0.0", port), AgentHandler)
    print(f"Archie Remediator Agent running on port {port}")
    server.serve_forever()
