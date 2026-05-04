"""
AWS Bedrock Full Agent Stack Template

Complete AI agent infrastructure with:
- AgentCore Runtime with custom container support
- AgentCore Memory for conversation persistence
- AgentCore Code Interpreter (optional)
- ECR Repository for agent container images
- IAM roles with least-privilege permissions
- CloudWatch observability

Base cost: ~$5-20/mo + per-invocation
"""

from typing import Any, Dict, Optional
from pathlib import Path
import json as _json
import time as _time
import pulumi
import pulumi_aws as aws

from provisioner.templates.base import InfrastructureTemplate, template_registry
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory
from provisioner.utils.aws import ResourceNamer, get_standard_tags


def _wait_for_iam(arn):
    """Wait for IAM eventual consistency before using role ARN"""
    _time.sleep(60)
    return arn


@template_registry("aws-bedrock-agent-stack")
class BedrockAgentStackTemplate(InfrastructureTemplate):
    """
    Full Bedrock Agent Stack — runtime + memory + ECR + observability.

    Creates:
    - ECR Repository for agent container images
    - IAM role with Bedrock + ECR + Logs permissions
    - AgentCore Agent Runtime with custom container
    - AgentCore Runtime Endpoint
    - AgentCore Memory for conversation persistence
    - AgentCore Code Interpreter (optional)
    - CloudWatch Log Group
    """

    def __init__(self, name: str = None, config: Dict[str, Any] = None, aws_config: Dict[str, Any] = None, **kwargs):
        raw_config = config or aws_config or kwargs or {}
        if name is None:
            name = (
                raw_config.get('project_name') or
                raw_config.get('projectName') or
                raw_config.get('parameters', {}).get('aws', {}).get('project_name') or
                'agent-stack'
            )
        super().__init__(name, raw_config)
        self.config = raw_config

        # Resource references
        self.ecr_repo: Optional[object] = None
        self.agent_role: Optional[object] = None
        self.agent_runtime: Optional[object] = None
        self.agent_endpoint: Optional[object] = None
        self.agent_memory: Optional[object] = None
        self.code_interpreter: Optional[object] = None
        self.log_group: Optional[object] = None

    def _cfg(self, key: str, default=None):
        """Read config from both root and parameters levels (Rule #6)"""
        params = self.config.get('parameters', {})
        aws_params = params.get('aws', {}) if isinstance(params, dict) else {}
        return (
            self.config.get(key) or
            (aws_params.get(key) if isinstance(aws_params, dict) else None) or
            (params.get(key) if isinstance(params, dict) else None) or
            default
        )

    def create_infrastructure(self) -> Dict[str, Any]:
        """Deploy agent stack infrastructure (implements abstract method)"""
        return self.create()

    def create(self) -> Dict[str, Any]:
        """Deploy complete Bedrock Agent Stack using factory pattern"""
        project = self._cfg('project_name', 'myagent')
        env = self._cfg('environment', 'dev')
        agent_name = self._cfg('agent_name', project)
        model_id = self._cfg('model_id', 'us.anthropic.claude-sonnet-4-20250514-v1:0')
        system_prompt = self._cfg('system_prompt', 'You are an Archie DevOps Agent — an AI infrastructure assistant that manages cloud stacks through the Archie platform.')
        team_name = self._cfg('team_name', '')
        enable_memory = self._cfg('enable_memory', True)
        enable_code_interpreter = self._cfg('enable_code_interpreter', False)
        container_uri = self._cfg('container_uri', '416851285955.dkr.ecr.us-east-1.amazonaws.com/archie-agentcore-insurance:latest')
        archie_token = self._cfg('archie_api_key', '') or self._cfg('archie_token', '')

        safe_name = agent_name.replace('-', '_').replace(' ', '_')
        namer = ResourceNamer(project=project, environment=env, region='us-east-1', template='aws-bedrock-agent-stack')
        tags = get_standard_tags(project=project, environment=env, template='bedrock-agent-stack')
        tags['ManagedBy'] = 'Archie'
        tags.update(self._cfg('tags', {}))
        if team_name:
            tags['Team'] = team_name

        # 1. ECR Repository — store agent container images
        ecr_name = f"ecr-{project}-agent-{env}"
        self.ecr_repo = factory.create(
            "aws:ecr:Repository",
            ecr_name,
            name=f"{project}-agent-{env}",
            image_tag_mutability="MUTABLE",
            image_scanning_configuration={"scan_on_push": True},
            tags={**tags, "Name": ecr_name},
        )

        # 2. IAM Role for Agent execution
        assume_role_policy = _json.dumps({
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": {
                    "Service": [
                        "bedrock.amazonaws.com",
                        "bedrock-agentcore.amazonaws.com"
                    ]
                },
                "Action": "sts:AssumeRole"
            }]
        })

        role_name = f"role-agent-{project}-{env}"
        self.agent_role = factory.create(
            "aws:iam:Role",
            role_name,
            assume_role_policy=assume_role_policy,
            tags={**tags, "Name": role_name},
        )

        # Comprehensive policy: InvokeModel + ECR pull + Logs + AgentCore
        policy_name = f"policy-agent-{project}-{env}"
        agent_managed_policy = factory.create(
            "aws:iam:Policy",
            policy_name,
            policy=_json.dumps({
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
                        "Resource": ["arn:aws:bedrock:*::foundation-model/*", "arn:aws:bedrock:*:*:inference-profile/*"]
                    },
                    {
                        "Effect": "Allow",
                        "Action": ["ecr:GetDownloadUrlForLayer", "ecr:BatchGetImage"],
                        "Resource": "arn:aws:ecr:*:*:repository/*"
                    },
                    {
                        "Effect": "Allow",
                        "Action": ["ecr:GetAuthorizationToken"],
                        "Resource": "*"
                    },
                    {
                        "Effect": "Allow",
                        "Action": ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"],
                        "Resource": "arn:aws:logs:*:*:log-group:/aws/bedrock/*"
                    },
                    {
                        "Effect": "Allow",
                        "Action": [
                            "bedrock-agentcore:CreateAgentRuntime",
                            "bedrock-agentcore:InvokeAgentRuntime",
                            "bedrock-agentcore:UpdateAgentRuntime",
                            "bedrock-agentcore:DeleteAgentRuntime",
                        ],
                        "Resource": "arn:aws:bedrock-agentcore:*:*:runtime/*"
                    }
                ]
            }),
            tags={**tags, "Name": policy_name},
        )

        # Attach policy to role
        attach_name = f"attach-agent-{project}-{env}"
        agent_policy_attachment = factory.create(
            "aws:iam:RolePolicyAttachment",
            attach_name,
            role=self.agent_role.name,
            policy_arn=agent_managed_policy.arn,
        )

        # 3. CloudWatch Log Group
        log_name = f"logs-agent-{project}-{env}"
        self.log_group = factory.create(
            "aws:cloudwatch:LogGroup",
            log_name,
            name=f"/aws/bedrock/agent/{project}-{env}",
            retention_in_days=14,
            tags={**tags, "Name": log_name},
        )

        # 4. AgentCore Runtime — .apply() ensures role exists first
        runtime_name = f"runtime-{project}-{env}"
        self.agent_runtime = aws.bedrock.AgentcoreAgentRuntime(
            runtime_name,
            agent_runtime_name=f"{safe_name}_{env}",
            role_arn=self.agent_role.arn.apply(_wait_for_iam),
            description=f"Bedrock Agent for {project} ({env}) — {model_id}",
            agent_runtime_artifact={
                "container_configuration": {
                    "container_uri": container_uri,
                },
            },
            network_configuration=aws.bedrock.AgentcoreAgentRuntimeNetworkConfigurationArgs(
                network_mode="PUBLIC",
            ),
            environment_variables={
                "MODEL_ID": model_id,
                "SYSTEM_PROMPT": system_prompt,
                "ENVIRONMENT": env,
                "ARCHIE_API": "https://9eumbz9bog.execute-api.us-east-1.amazonaws.com",
                "ARCHIE_TOKEN": archie_token,
                "PROJECT": project,
            },
            tags={**tags, "Name": runtime_name},
            opts=pulumi.ResourceOptions(depends_on=[self.agent_role, agent_policy_attachment]),
        )

        # 5. AgentCore Runtime Endpoint
        endpoint_name = f"endpoint-{project}-{env}"
        self.agent_endpoint = aws.bedrock.AgentcoreAgentRuntimeEndpoint(
            endpoint_name,
            agent_runtime_id=self.agent_runtime.agent_runtime_id,
            name=f"{safe_name}_endpoint_{env}",
            description=f"Endpoint for {agent_name} ({env})",
            tags={**tags, "Name": endpoint_name},
        )

        # 6. AgentCore Memory (optional — conversation persistence)
        if enable_memory:
            memory_name = f"memory-{project}-{env}"
            self.agent_memory = aws.bedrock.AgentcoreMemory(
                memory_name,
                event_expiry_duration=30,  # days (7-365)
                name=f"{safe_name}_memory_{env}",
                tags={**tags, "Name": memory_name},
            )
            pulumi.export('memory_id', self.agent_memory.id)

        # 7. AgentCore Code Interpreter (optional — lets agent run code)
        if enable_code_interpreter:
            codeinterp_name = f"codeinterp-{project}-{env}"
            self.code_interpreter = aws.bedrock.AgentcoreCodeInterpreter(
                codeinterp_name,
                name=f"{safe_name}_codeinterp_{env}",
                tags={**tags, "Name": codeinterp_name},
            )
            pulumi.export('code_interpreter_id', self.code_interpreter.id)

        # Exports (Rule #7 — export all generated values)
        pulumi.export('agent_name', agent_name)
        pulumi.export('model_id', model_id)
        pulumi.export('agent_runtime_id', self.agent_runtime.agent_runtime_id)
        pulumi.export('agent_runtime_arn', self.agent_runtime.agent_runtime_arn)
        pulumi.export('endpoint_id', self.agent_endpoint.id)
        pulumi.export('ecr_repository_url', self.ecr_repo.repository_url)
        pulumi.export('agent_role_arn', self.agent_role.arn)
        pulumi.export('log_group_name', self.log_group.name)
        pulumi.export('environment', env)
        pulumi.export('team_name', team_name)

        return self.get_outputs()

    def get_outputs(self) -> Dict[str, Any]:
        """Get outputs for this template (implements abstract method)"""
        outputs = {
            "agent_runtime_id": self.agent_runtime.agent_runtime_id if self.agent_runtime else None,
            "agent_runtime_arn": self.agent_runtime.agent_runtime_arn if self.agent_runtime else None,
            "endpoint_id": self.agent_endpoint.id if self.agent_endpoint else None,
            "ecr_repository_url": self.ecr_repo.repository_url if self.ecr_repo else None,
            "agent_role_arn": self.agent_role.arn if self.agent_role else None,
            "log_group_name": self.log_group.name if self.log_group else None,
        }
        if self.agent_memory:
            outputs["memory_id"] = self.agent_memory.id
        if self.code_interpreter:
            outputs["code_interpreter_id"] = self.code_interpreter.id
        return outputs

    @classmethod
    def get_metadata(cls) -> Dict[str, Any]:
        """Get template metadata (SOURCE OF TRUTH for extractor)"""
        return {
            "name": "aws-bedrock-agent-stack",
            "title": "Agent Runtime (AgentCore)",
            "description": "Complete AI agent infrastructure: AgentCore Runtime with custom containers, conversation memory, code interpreter, ECR, IAM, and CloudWatch.",
            "category": "ai",
            "version": "1.0.0",
            "author": "Archie",
            "cloud": "aws",
            "environment": "nonprod",
            "base_cost": "$5-20/month + per-invocation",
            "features": [
                "AgentCore Runtime with custom container support",
                "ECR Repository for agent images (scan on push)",
                "Conversation memory persistence (30-day retention)",
                "Optional Code Interpreter for dynamic code execution",
                "IAM least-privilege with ECR pull + Bedrock invoke",
                "CloudWatch logs for observability",
                "Configurable foundation model (Claude, Nova, etc.)",
            ],
            "tags": ["ai", "bedrock", "agentcore", "agent", "llm", "ecr", "memory"],
            "deployment_time": "3-5 minutes",
            "complexity": "intermediate",
            "use_cases": [
                "Production AI agent deployment",
                "DevOps automation agents (Archie DevOps Agent)",
                "Strands SDK agent hosting with custom containers",
                "Code-executing research agents",
                "Customer support with conversation memory",
            ],
            "pillars": [
                {
                    "title": "Security",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Least-privilege IAM, ECR image scanning, scoped model access",
                    "practices": [
                        "Dedicated IAM role with minimal Bedrock + ECR permissions",
                        "ECR image scanning on push for vulnerability detection",
                        "Model access scoped to foundation-model and inference-profile ARNs",
                        "Managed policy (not inline) for clean permission boundaries",
                        "CloudWatch audit trail for all agent invocations",
                    ]
                },
                {
                    "title": "Operational Excellence",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Full observability with memory persistence and health monitoring",
                    "practices": [
                        "CloudWatch logs with 14-day retention for debugging",
                        "Conversation memory for multi-turn agent interactions",
                        "Infrastructure as Code with Pulumi for repeatable deployments",
                        "Configurable system prompt without container rebuild",
                        "Runtime endpoint with health status monitoring",
                    ]
                },
                {
                    "title": "Cost Optimization",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Pay-per-invocation with optional components to control costs",
                    "practices": [
                        "Base runtime costs only when invoked",
                        "Memory and Code Interpreter are optional toggles",
                        "ECR lifecycle policies can reduce storage costs",
                        "Single runtime serves multiple use cases",
                    ]
                },
                {
                    "title": "Reliability",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "AWS-managed runtime with auto-scaling and conversation persistence",
                    "practices": [
                        "AWS-managed infrastructure with built-in redundancy",
                        "Automatic scaling based on invocation volume",
                        "Conversation memory survives runtime restarts",
                        "Public endpoint with AWS edge network",
                    ]
                },
                {
                    "title": "Sustainability",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Serverless architecture with no idle compute waste",
                    "practices": [
                        "No idle compute — scales to zero between invocations",
                        "Optional components reduce unnecessary resource consumption",
                        "Shared ECR registry avoids duplicate image storage",
                    ]
                },
            ],
        }

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        """Get configuration schema (SOURCE OF TRUTH for extractor)"""
        return {
            "type": "object",
            "properties": {
                "project_name": {
                    "type": "string",
                    "default": "myagent",
                    "title": "Project Name",
                    "description": "Name for the agent project (used in resource naming)",
                    "order": 1,
                    "group": "Essentials",
                    "isEssential": True,
                },
                "environment": {
                    "type": "string",
                    "default": "dev",
                    "title": "Environment",
                    "description": "Deployment environment",
                    "enum": ["dev", "staging", "prod"],
                    "order": 2,
                    "group": "Essentials",
                    "isEssential": True,
                },
                "agent_name": {
                    "type": "string",
                    "default": "",
                    "title": "Agent Name",
                    "description": "Display name for the agent (defaults to project name)",
                    "order": 10,
                    "group": "Agent Configuration",
                },
                "model_id": {
                    "type": "string",
                    "default": "us.anthropic.claude-sonnet-4-20250514-v1:0",
                    "title": "Foundation Model",
                    "description": "Bedrock model ID for the agent",
                    "enum": [
                        "us.anthropic.claude-sonnet-4-20250514-v1:0",
                        "us.anthropic.claude-haiku-4-5-20251001-v1:0",
                        "us.amazon.nova-pro-v1:0",
                        "us.amazon.nova-lite-v1:0",
                    ],
                    "order": 11,
                    "group": "Agent Configuration",
                },
                "system_prompt": {
                    "type": "string",
                    "default": "You are an Archie DevOps Agent — an AI infrastructure assistant that manages cloud stacks through the Archie platform.",
                    "title": "System Prompt",
                    "description": "Instructions that define the agent's behavior and capabilities",
                    "format": "textarea",
                    "order": 12,
                    "group": "Agent Configuration",
                },
                "container_uri": {
                    "type": "string",
                    "default": "",
                    "title": "Container Image URI",
                    "description": "ECR image URI for the agent container (leave blank for default Archie agent)",
                    "order": 13,
                    "group": "Agent Configuration",
                },
                "archie_api_key": {
                    "type": "string",
                    "default": "",
                    "title": "Archie API Key",
                    "description": "API key for the agent to call Archie platform APIs (generate in Settings → API Keys)",
                    "order": 14,
                    "group": "Agent Configuration",
                    "sensitive": True,
                },
                "enable_memory": {
                    "type": "boolean",
                    "default": True,
                    "title": "Enable Conversation Memory",
                    "description": "Persist conversation history across agent sessions (30-day retention)",
                    "order": 20,
                    "group": "Features",
                    "cost_impact": "+$0-5/month",
                },
                "enable_code_interpreter": {
                    "type": "boolean",
                    "default": False,
                    "title": "Enable Code Interpreter",
                    "description": "Let the agent execute code dynamically during conversations",
                    "order": 21,
                    "group": "Features",
                    "cost_impact": "+$0-10/month",
                },
                "team_name": {
                    "type": "string",
                    "default": "",
                    "title": "Team Name",
                    "description": "Team that owns this agent (added as resource tag)",
                    "order": 50,
                    "group": "Tags",
                },
            },
            "required": ["project_name"],
        }
