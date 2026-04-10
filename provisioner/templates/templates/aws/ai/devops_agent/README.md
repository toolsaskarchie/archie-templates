# Archie DevOps Agent

AI agent that manages your Archie infrastructure through natural language.

## Architecture

```
User → AgentCore Runtime (managed micro VM)
         ↓ Claude Sonnet 4 (Bedrock)
         ↓ 5 API Tools → Archie REST API
         ↓ Response with real infrastructure data
```

## Tools

| Tool | API Call | What it does |
|------|----------|-------------|
| list_stacks | GET /stacks | List all deployed stacks |
| get_stack | GET /stacks/{id} | Get stack details, resources, outputs |
| check_drift | POST /stacks/{id}/drift/check | Trigger drift detection |
| get_drift | GET /stacks/{id}/drift | Get drift status and drifted resources |
| list_blueprints | GET /marketplace/templates | Browse available blueprints |

## Container

The agent runs as a Docker container on AgentCore:

```bash
# Build
podman build --platform linux/arm64 -t your-ecr-repo:latest .

# Push
aws ecr get-login-password | podman login --username AWS --password-stdin your-ecr-uri
podman push your-ecr-repo:latest
```

## Files

- `agent.py` — Agent code with tools, system prompt, and HTTP server
- `Dockerfile` — Container image (Python 3.11 + boto3)
- `pulumi.py` — Archie template (Full Agent Stack: ECR + IAM + Runtime + Memory + Endpoint)
- `../agentcore_runtime/pulumi.py` — Minimal template (IAM + Runtime + Endpoint)

## Deploy

Fork from the Archie starter library → configure model + system prompt → deploy.
The template creates all infrastructure. Push your custom agent container to the ECR repo.
