"""
Archie Orchestrator — single entry point that routes to specialist agents.
User talks to "Archie". Archie delegates to Analyst, Auditor, Planner, or Triage.
"""
import os, json, boto3
from http.server import HTTPServer, BaseHTTPRequestHandler

MODEL_ID = os.environ.get("MODEL_ID", "us.anthropic.claude-sonnet-4-20250514-v1:0")

ANALYST_ARN = os.environ.get("ANALYST_AGENT_ARN", "")
AUDITOR_ARN = os.environ.get("AUDITOR_AGENT_ARN", "")
PLANNER_ARN = os.environ.get("PLANNER_AGENT_ARN", "")
TRIAGE_ARN = os.environ.get("TRIAGE_AGENT_ARN", "")

SYSTEM_PROMPT = os.environ.get("SYSTEM_PROMPT", """You are Archie — the AI infrastructure management assistant. Users talk to you in natural language. You route their requests to the right specialist agent.

Your specialists:
1. **Analyst** — dependency tracing, impact analysis, "what breaks if I delete X", blast radius
2. **Auditor** — compliance scanning, security reports, SOC2/ISO checks, "are my stacks secure?"
3. **Planner** — multi-stack deployment planning, "set up project falcon", orchestrated deploys
4. **Triage** — incident investigation, "something's wrong", correlates drift + health across stacks

Rules:
- Route EVERY infrastructure question to a specialist — never guess or make up data
- You can chain agents: "check status then generate a compliance report" → Triage then Auditor
- Summarize specialist responses clearly — add context, don't just forward
- For ambiguous requests, route to the most likely specialist and note your reasoning
- If a request spans multiple domains, call multiple specialists in sequence""")

bedrock = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION", "us-east-1"))
agentcore = boto3.client("bedrock-agentcore", region_name=os.environ.get("AWS_REGION", "us-east-1"))

TOOLS = [
    {"name": "ask_analyst", "description": "Ask the Analyst about dependencies, impact analysis, and blast radius. Use for: 'what depends on this VPC', 'what breaks if I delete X', 'show dependency tree'.",
     "input_schema": {"type": "object", "properties": {"question": {"type": "string"}}, "required": ["question"]}},
    {"name": "ask_auditor", "description": "Ask the Auditor for compliance scans and security reports. Use for: 'are my stacks compliant', 'generate security report', 'check for encryption gaps'.",
     "input_schema": {"type": "object", "properties": {"question": {"type": "string"}}, "required": ["question"]}},
    {"name": "ask_planner", "description": "Ask the Planner to plan or execute multi-stack deployments. Use for: 'deploy project falcon', 'set up a web app', 'what blueprints do I need'.",
     "input_schema": {"type": "object", "properties": {"instruction": {"type": "string"}}, "required": ["instruction"]}},
    {"name": "ask_triage", "description": "Ask Triage to investigate incidents. Use for: 'something is broken', 'investigate production', 'why is my ALB unhealthy', 'summarize all issues'.",
     "input_schema": {"type": "object", "properties": {"question": {"type": "string"}}, "required": ["question"]}},
]


def invoke_agent(arn, message):
    if not arn: return {"error": "Agent not configured — missing runtime ARN"}
    try:
        resp = agentcore.invoke_agent_runtime(agentRuntimeArn=arn, payload=json.dumps({"input": message}).encode())
        result = json.loads(resp["response"].read())
        return {"response": result.get("output", str(result))}
    except Exception as e: return {"error": f"Agent failed: {e}"}


def execute_tool(name, inp):
    if name == "ask_analyst": return invoke_agent(ANALYST_ARN, inp.get("question", ""))
    elif name == "ask_auditor": return invoke_agent(AUDITOR_ARN, inp.get("question", ""))
    elif name == "ask_planner": return invoke_agent(PLANNER_ARN, inp.get("instruction", ""))
    elif name == "ask_triage": return invoke_agent(TRIAGE_ARN, inp.get("question", ""))
    return {"error": f"Unknown tool: {name}"}


def agent_conversation(user_message):
    messages = [{"role": "user", "content": user_message}]
    for _ in range(6):
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
        self.wfile.write(json.dumps({"status": "healthy", "agent": "archie-orchestrator"}).encode())
    def log_message(self, *a): pass

if __name__ == "__main__":
    HTTPServer(("0.0.0.0", int(os.environ.get("PORT", "8080"))), H).serve_forever()
