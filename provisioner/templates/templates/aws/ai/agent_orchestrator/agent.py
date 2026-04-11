"""
Archie Orchestrator Agent — single entry point that routes to specialist agents.
Understands user intent and delegates to Monitor, Deployer, or Remediator.
"""
import os
import json
import urllib.request
import urllib.error
import boto3
from http.server import HTTPServer, BaseHTTPRequestHandler

MODEL_ID = os.environ.get("MODEL_ID", "us.anthropic.claude-sonnet-4-20250514-v1:0")
ARCHIE_API = os.environ.get("ARCHIE_API", "https://9eumbz9bog.execute-api.us-east-1.amazonaws.com")

# Agent runtime ARNs — set via env vars at deploy time
MONITOR_ARN = os.environ.get("MONITOR_AGENT_ARN", "")
DEPLOYER_ARN = os.environ.get("DEPLOYER_AGENT_ARN", "")
REMEDIATOR_ARN = os.environ.get("REMEDIATOR_AGENT_ARN", "")

SYSTEM_PROMPT = os.environ.get("SYSTEM_PROMPT", """You are Archie — an AI infrastructure management assistant. You coordinate three specialist agents:

1. **Monitor** — reads infrastructure status, lists stacks, checks drift, browses blueprints. Use for questions like "what's my infra status?", "show my stacks", "any drift?"
2. **Deployer** — deploys new infrastructure from blueprints. Use for "deploy a VPC", "create a new stack", "set up a database"
3. **Remediator** — fixes configuration drift. Use for "fix drifted stacks", "remediate drift", "restore my infrastructure"

RULES:
- Route EVERY user request to the right specialist agent via the tools
- You can chain agents: "check status then fix drift" → call monitor, then remediator
- For ambiguous requests, ask the user to clarify
- NEVER make up infrastructure data — always delegate to an agent
- Summarize agent responses clearly — don't just pass through raw output
- For destructive actions (deploy, remediate), confirm the agent asked for user confirmation""")

bedrock = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION", "us-east-1"))
agentcore = boto3.client("bedrock-agentcore", region_name=os.environ.get("AWS_REGION", "us-east-1"))

TOOLS = [
    {
        "name": "ask_monitor",
        "description": "Ask the Monitor agent about infrastructure status. Use for: listing stacks, checking drift status, viewing stack details, browsing blueprints. Read-only — never modifies anything.",
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "The question to ask the Monitor agent (e.g. 'list all stacks', 'check drift on all stacks', 'what blueprints are available')"}
            },
            "required": ["question"]
        }
    },
    {
        "name": "ask_deployer",
        "description": "Ask the Deployer agent to deploy infrastructure. Use for: deploying new stacks, browsing templates, configuring deployments. Will ask user for confirmation before deploying.",
        "input_schema": {
            "type": "object",
            "properties": {
                "instruction": {"type": "string", "description": "The deployment instruction (e.g. 'deploy a VPC named falcon in dev', 'what templates are available for databases')"}
            },
            "required": ["instruction"]
        }
    },
    {
        "name": "ask_remediator",
        "description": "Ask the Remediator agent to fix configuration drift. Use for: checking drift details, previewing remediation, applying fixes. Will ask user for confirmation before applying.",
        "input_schema": {
            "type": "object",
            "properties": {
                "instruction": {"type": "string", "description": "The remediation instruction (e.g. 'fix all drifted stacks', 'preview remediation on sunshine-vnet', 'apply remediation')"}
            },
            "required": ["instruction"]
        }
    },
]


def invoke_agent(agent_arn, message):
    """Invoke a specialist agent and return its response."""
    if not agent_arn:
        return {"error": "Agent not configured — missing runtime ARN"}
    try:
        resp = agentcore.invoke_agent_runtime(
            agentRuntimeArn=agent_arn,
            payload=json.dumps({"input": message}).encode(),
        )
        result = json.loads(resp["response"].read())
        return {"response": result.get("output", str(result))}
    except Exception as e:
        return {"error": f"Agent invocation failed: {str(e)}"}


def execute_tool(name, input_data):
    if name == "ask_monitor":
        return invoke_agent(MONITOR_ARN, input_data.get("question", ""))
    elif name == "ask_deployer":
        return invoke_agent(DEPLOYER_ARN, input_data.get("instruction", ""))
    elif name == "ask_remediator":
        return invoke_agent(REMEDIATOR_ARN, input_data.get("instruction", ""))
    return {"error": f"Unknown tool: {name}"}


def agent_conversation(user_message):
    messages = [{"role": "user", "content": user_message}]
    for _ in range(6):
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
        self.wfile.write(json.dumps({"status": "healthy", "agent": "archie-orchestrator"}).encode())

    def log_message(self, format, *args):
        pass

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    server = HTTPServer(("0.0.0.0", port), AgentHandler)
    print(f"Archie Orchestrator Agent running on port {port}")
    server.serve_forever()
