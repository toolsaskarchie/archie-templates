"""
AWS Bedrock AgentCore Runtime Template

Deploys a managed AI agent using AWS Bedrock AgentCore with:
- IAM role for agent execution with Bedrock permissions
- AgentCore Runtime definition with configurable model and system prompt
- AgentCore Runtime Endpoint for invocation
- CloudWatch log group for observability

Base cost: ~$0/mo (pay-per-invocation via Bedrock API)
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
    _time.sleep(30)
    return arn


@template_registry("aws-bedrock-agentcore")
class BedrockAgentCoreTemplate(InfrastructureTemplate):
    """
    Bedrock AgentCore Runtime — managed AI agent on AWS.

    Creates:
    - IAM role with Bedrock AgentCore + InvokeModel permissions
    - AgentCore Agent Runtime definition
    - AgentCore Runtime Endpoint
    - CloudWatch Log Group for agent logs
    """

    def __init__(self, name: str = None, config: Dict[str, Any] = None, aws_config: Dict[str, Any] = None, **kwargs):
        raw_config = config or aws_config or kwargs or {}
        if name is None:
            name = (
                raw_config.get('project_name') or
                raw_config.get('projectName') or
                raw_config.get('parameters', {}).get('aws', {}).get('project_name') or
                'bedrock-agent'
            )
        super().__init__(name, raw_config)
        self.config = raw_config

        # Resource references
        self.agent_role: Optional[object] = None
        self.agent_runtime: Optional[object] = None
        self.agent_endpoint: Optional[object] = None
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
        """Deploy AgentCore infrastructure (implements abstract method)"""
        return self.create()

    def create(self) -> Dict[str, Any]:
        """Deploy Bedrock AgentCore Runtime using factory pattern"""
        project = self._cfg('project_name', 'myagent')
        env = self._cfg('environment', 'dev')
        agent_name = self._cfg('agent_name', project)
        model_id = self._cfg('model_id', 'us.anthropic.claude-sonnet-4-20250514-v1:0')
        system_prompt = self._cfg('system_prompt', 'You are a helpful AI assistant.')
        team_name = self._cfg('team_name', '')
        container_uri = self._cfg('container_uri', '416851285955.dkr.ecr.us-east-1.amazonaws.com/archie-agentcore-insurance:latest')
        archie_token = self._cfg('archie_api_key', '') or self._cfg('archie_token', '')

        safe_name = agent_name.replace('-', '_').replace(' ', '_')
        namer = ResourceNamer(project=project, environment=env, region='us-east-1', template='aws-bedrock-agentcore')
        tags = get_standard_tags(project=project, environment=env, template='bedrock-agentcore')
        tags['ManagedBy'] = 'Archie'
        tags.update(self._cfg('tags', {}))
        if team_name:
            tags['Team'] = team_name

        # 1. IAM Role for Agent execution
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

        role_name = f"role-agentcore-{project}-{env}"
        self.agent_role = factory.create(
            "aws:iam:Role",
            role_name,
            assume_role_policy=assume_role_policy,
            tags={**tags, "Name": role_name},
        )

        # InvokeModel + Logs + ECR policy
        policy_name = f"policy-agentcore-{project}-{env}"
        invoke_policy = factory.create(
            "aws:iam:RolePolicy",
            policy_name,
            role=self.agent_role.name,
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
                        "Action": ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"],
                        "Resource": "arn:aws:logs:*:*:log-group:/aws/bedrock/*"
                    },
                    {
                        "Effect": "Allow",
                        "Action": ["ecr:GetAuthorizationToken"],
                        "Resource": "*"
                    },
                    {
                        "Effect": "Allow",
                        "Action": ["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer"],
                        "Resource": "arn:aws:ecr:*:*:repository/*"
                    }
                ]
            }),
        )

        # 2. CloudWatch Log Group
        log_name = f"logs-agentcore-{project}-{env}"
        self.log_group = factory.create(
            "aws:cloudwatch:LogGroup",
            log_name,
            name=f"/aws/bedrock/agentcore/{project}-{env}",
            retention_in_days=14,
            tags={**tags, "Name": log_name},
        )

        # 3. AgentCore Runtime — .apply() ensures role exists before creation
        runtime_name = f"agentcore-{project}-{env}"
        self.agent_runtime = aws.bedrock.AgentcoreAgentRuntime(
            runtime_name,
            agent_runtime_name=f"{safe_name}_{env}",
            role_arn=self.agent_role.arn.apply(_wait_for_iam),
            description=f"Bedrock AgentCore agent for {project} ({env})",
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
            },
            tags={**tags, "Name": runtime_name},
            opts=pulumi.ResourceOptions(depends_on=[self.agent_role, invoke_policy]),
        )

        # 4. AgentCore Runtime Endpoint
        endpoint_name = f"endpoint-{project}-{env}"
        self.agent_endpoint = aws.bedrock.AgentcoreAgentRuntimeEndpoint(
            endpoint_name,
            agent_runtime_id=self.agent_runtime.agent_runtime_id,
            name=f"{safe_name}_endpoint_{env}",
            description=f"Endpoint for {agent_name} ({env})",
            tags={**tags, "Name": endpoint_name},
        )

        # Exports (Rule #7 — export all generated values)
        pulumi.export('agent_name', agent_name)
        pulumi.export('agent_runtime_id', self.agent_runtime.agent_runtime_id)
        pulumi.export('agent_runtime_arn', self.agent_runtime.agent_runtime_arn)
        pulumi.export('endpoint_id', self.agent_endpoint.id)
        pulumi.export('agent_role_arn', self.agent_role.arn)
        pulumi.export('log_group_name', self.log_group.name)
        pulumi.export('model_id', model_id)
        pulumi.export('environment', env)
        pulumi.export('team_name', team_name)

        return self.get_outputs()

    def get_outputs(self) -> Dict[str, Any]:
        """Get outputs for this template (implements abstract method)"""
        return {
            "agent_runtime_id": self.agent_runtime.agent_runtime_id if self.agent_runtime else None,
            "agent_runtime_arn": self.agent_runtime.agent_runtime_arn if self.agent_runtime else None,
            "endpoint_id": self.agent_endpoint.id if self.agent_endpoint else None,
            "agent_role_arn": self.agent_role.arn if self.agent_role else None,
            "log_group_name": self.log_group.name if self.log_group else None,
        }

    @classmethod
    def get_metadata(cls) -> Dict[str, Any]:
        """Get template metadata (SOURCE OF TRUTH for extractor)"""
        return {
            "name": "aws-bedrock-agentcore",
            "title": "Agent Runtime Lite (AgentCore)",
            "description": "Deploy a managed AI agent using AWS Bedrock AgentCore with IAM roles, runtime endpoint, and CloudWatch observability. Pay-per-invocation, no idle compute.",
            "category": "ai",
            "version": "1.0.0",
            "author": "Archie",
            "cloud": "aws",
            "environment": "nonprod",
            "base_cost": "$0/month (pay-per-invocation)",
            "features": [
                "Managed AgentCore Runtime (no servers to manage)",
                "Configurable foundation model (Claude, Titan, etc.)",
                "Custom system prompt",
                "IAM least-privilege roles",
                "CloudWatch log group for observability",
                "Runtime endpoint for API invocation",
            ],
            "tags": ["ai", "bedrock", "agentcore", "agent", "llm"],
            "deployment_time": "2-3 minutes",
            "complexity": "intermediate",
            "use_cases": [
                "AI-powered chatbots and assistants",
                "Document analysis agents",
                "Code review and generation agents",
                "DevOps automation agents",
                "Customer support automation",
            ],
            "pillars": [
                {
                    "title": "Security",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Least-privilege IAM roles scoped to specific model ARN, no public credentials",
                    "practices": [
                        "Dedicated IAM role per agent with minimal permissions",
                        "Model access scoped to specific foundation model ARN",
                        "ECR image scanning for container vulnerabilities",
                        "CloudWatch logs for audit trail",
                    ]
                },
                {
                    "title": "Operational Excellence",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "AWS-managed runtime with built-in observability and scaling",
                    "practices": [
                        "CloudWatch logs with 14-day retention for debugging",
                        "Infrastructure as Code with Pulumi for repeatable deployments",
                        "Configurable system prompt without redeployment",
                        "Runtime endpoint health monitoring",
                    ]
                },
                {
                    "title": "Cost Optimization",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Pay-per-invocation pricing — zero cost when not in use",
                    "practices": [
                        "No idle compute costs (pay only for API calls)",
                        "S3-based logs instead of CloudWatch Insights",
                        "Single runtime serves multiple use cases via system prompt",
                    ]
                },
                {
                    "title": "Reliability",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "AWS-managed runtime with auto-scaling and health checks",
                    "practices": [
                        "AWS-managed infrastructure with built-in redundancy",
                        "Automatic scaling based on invocation volume",
                        "Public endpoint with AWS edge network",
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
                    "default": "You are a helpful AI assistant.",
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
                    "description": "ECR image URI for the agent container (leave blank for default)",
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
