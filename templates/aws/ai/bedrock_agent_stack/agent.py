"""
Archie DevOps Agent — runs on AWS Bedrock AgentCore
Manages infrastructure through the Archie API using natural language.
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

SYSTEM_PROMPT = """You are an Archie DevOps Agent — an AI infrastructure assistant that manages cloud stacks through the Archie platform.

You have access to these tools:
1. list_stacks — List all deployed infrastructure stacks
2. get_stack — Get details of a specific stack by ID
3. check_drift — Trigger drift detection on a stack
4. get_drift — Get drift status for a stack
5. list_blueprints — List available blueprints in the catalog

When the user asks about their infrastructure, USE the tools to get real data. Don't make up stack names or statuses.

Format your responses clearly:
- Use bullet points for lists
- Show stack names in bold
- Include status, cloud provider, and environment
- If drift is detected, highlight it as urgent

You are helpful, concise, and proactive. If you see issues (drift, failed stacks, outdated versions), flag them."""

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
    """Call the Archie REST API."""
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
    """Execute a tool and return the result."""
    if name == "list_stacks":
        result = call_archie_api("/stacks")
        if isinstance(result, list):
            stacks = []
            for s in result[:20]:
                stacks.append({
                    "id": s.get("deploymentId", ""),
                    "name": s.get("display_name") or s.get("stack_name", ""),
                    "template": s.get("template_name", ""),
                    "status": s.get("status", ""),
                    "cloud": s.get("cloud", "aws"),
                    "environment": s.get("environment", "dev"),
                    "resource_count": s.get("resource_count", 0),
                    "drift_status": s.get("drift_status", "unknown"),
                })
            return {"stacks": stacks, "total": len(result)}
        return result
    
    elif name == "get_stack":
        stack_id = input_data.get("stack_id", "")
        result = call_archie_api(f"/stacks/{stack_id}")
        return result
    
    elif name == "check_drift":
        stack_id = input_data.get("stack_id", "")
        result = call_archie_api(f"/stacks/{stack_id}/drift/check", method="POST")
        return result
    
    elif name == "get_drift":
        stack_id = input_data.get("stack_id", "")
        result = call_archie_api(f"/stacks/{stack_id}/drift")
        return result
    
    elif name == "list_blueprints":
        result = call_archie_api("/marketplace/templates")
        if isinstance(result, list):
            bps = []
            for b in result[:20]:
                bps.append({
                    "name": b.get("action_name") or b.get("id", ""),
                    "title": b.get("title", ""),
                    "cloud": b.get("cloud", ""),
                    "category": b.get("category", ""),
                    "description": b.get("description", "")[:100],
                })
            return {"blueprints": bps, "total": len(result)}
        return result
    
    return {"error": f"Unknown tool: {name}"}


def agent_conversation(user_message):
    """Run agent loop with tool use."""
    messages = [{"role": "user", "content": user_message}]
    
    for _ in range(5):  # Max 5 tool-use rounds
        response = bedrock.invoke_model(
            modelId=MODEL_ID,
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 2048,
                "system": SYSTEM_PROMPT,
                "messages": messages,
                "tools": TOOLS,
            }),
            contentType="application/json",
        )
        result = json.loads(response["body"].read())
        
        # Check if model wants to use a tool
        stop_reason = result.get("stop_reason", "")
        content = result.get("content", [])
        
        if stop_reason == "tool_use":
            # Find tool use blocks
            tool_results = []
            assistant_content = []
            for block in content:
                assistant_content.append(block)
                if block.get("type") == "tool_use":
                    tool_name = block["name"]
                    tool_input = block.get("input", {})
                    tool_result = execute_tool(tool_name, tool_input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block["id"],
                        "content": json.dumps(tool_result),
                    })
            
            # Add assistant response and tool results to conversation
            messages.append({"role": "assistant", "content": assistant_content})
            messages.append({"role": "user", "content": tool_results})
        else:
            # Final text response
            text_parts = [b.get("text", "") for b in content if b.get("type") == "text"]
            return "\n".join(text_parts)
    
    return "I ran out of tool-use rounds. Please try a simpler question."


class AgentHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(content_length)) if content_length else {}
        
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
        self.wfile.write(json.dumps({"status": "healthy", "agent": "archie-devops"}).encode())
    
    def log_message(self, format, *args):
        pass  # Suppress noisy HTTP logs

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    server = HTTPServer(("0.0.0.0", port), AgentHandler)
    print(f"Archie DevOps Agent running on port {port}")
    server.serve_forever()
