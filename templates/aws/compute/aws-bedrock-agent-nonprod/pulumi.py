from typing import Any, Dict, Optional, List
from pathlib import Path
import pulumi
import pulumi_aws as aws

from provisioner.templates.base import InfrastructureTemplate, template_registry
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory
from provisioner.templates.template_config import TemplateConfig
from provisioner.utils.aws import ResourceNamer, get_standard_tags
from provisioner.utils.aws.naming import sanitize_name

@template_registry("aws-bedrock-agent-nonprod")
class BedrockAgentTemplate(InfrastructureTemplate):
    def __init__(self, name: str = None, config: Dict[str, Any] = None, **kwargs):
        raw_config = config or kwargs or {}
        if name is None:
            name = raw_config.get('project_name', 'bedrock-agent')
        name = sanitize_name(name, 32)
        super().__init__(name, raw_config)
        template_dir = Path(__file__).parent
        self.config_loader = TemplateConfig(template_dir, raw_config)
        self.agent_role = None
        self.model_role = None
        self.log_group = None
        self.agent = None

    def create_infrastructure(self) -> Dict[str, Any]:
        return self.create()

    def create(self) -> Dict[str, Any]:
        params = self.config.get('parameters', {})
        def cfg(key, default=None):
            return self.config.get(key) or params.get(key) or default

        project = cfg('project_name', 'myapp')
        team_name = cfg('team_name', '')
        env = cfg('environment', 'dev')
        region = cfg('region', 'us-east-1')
        agent_name = cfg('agent_name')
        model_id = cfg('model_id', 'anthropic.claude-sonnet-4-20250514')
        system_prompt = cfg('system_prompt')

        namer = ResourceNamer(
            project=project,
            environment=env,
            region=region,
            template="aws-bedrock-agent-nonprod"
        )
        
        tags = get_standard_tags(
            project=project,
            environment=env,
            template="bedrock-agent"
        )
        tags.update({
            "managed_by": "archie",
            "team": cfg('team', 'platform')
        })

        # CloudWatch Log Group for agent observability
        self.log_group = factory.create("aws:cloudwatch:LogGroup", f"{self.name}-log-group",
            name=f"/aws/bedrock/agent/{agent_name}",
            retention_in_days=7,
            tags={**tags, "Name": namer.resource("logs")})

        # IAM role for agent with Bedrock AgentCore permissions
        agent_assume_role_policy = {
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": {
                    "Service": "bedrock.amazonaws.com"
                },
                "Action": "sts:AssumeRole"
            }]
        }

        self.agent_role = factory.create("aws:iam:Role", f"{self.name}-agent-role",
            name=namer.resource("agent-role"),
            assume_role_policy=pulumi.Output.from_input(agent_assume_role_policy).apply(lambda x: pulumi.Output.json_dumps(x)),
            tags={**tags, "Name": namer.resource("agent-role")})

        # Policy for agent permissions
        agent_policy = factory.create("aws:iam:Policy", f"{self.name}-agent-policy",
            name=namer.resource("agent-policy"),
            policy=pulumi.Output.all().apply(lambda _: pulumi.Output.json_dumps({
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": [
                            "bedrock:InvokeModel",
                            "bedrock:InvokeModelWithResponseStream"
                        ],
                        "Resource": f"arn:aws:bedrock:{region}::foundation-model/{model_id}"
                    },
                    {
                        "Effect": "Allow",
                        "Action": [
                            "logs:CreateLogStream",
                            "logs:PutLogEvents"
                        ],
                        "Resource": f"arn:aws:logs:{region}:*:log-group:/aws/bedrock/agent/{agent_name}:*"
                    }
                ]
            })),
            tags={**tags, "Name": namer.resource("agent-policy")})

        # Attach policy to agent role
        factory.create("aws:iam:RolePolicyAttachment", f"{self.name}-agent-policy-attachment",
            role=self.agent_role.name,
            policy_arn=agent_policy.arn)

        # IAM role for model invocation
        model_assume_role_policy = {
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": {
                    "Service": "bedrock.amazonaws.com"
                },
                "Action": "sts:AssumeRole"
            }]
        }

        self.model_role = factory.create("aws:iam:Role", f"{self.name}-model-role",
            name=namer.resource("model-role"),
            assume_role_policy=pulumi.Output.from_input(model_assume_role_policy).apply(lambda x: pulumi.Output.json_dumps(x)),
            tags={**tags, "Name": namer.resource("model-role")})

        # Policy for model invocation
        model_policy = factory.create("aws:iam:Policy", f"{self.name}-model-policy",
            name=namer.resource("model-policy"),
            policy=pulumi.Output.all().apply(lambda _: pulumi.Output.json_dumps({
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": [
                            "bedrock:InvokeModel",
                            "bedrock:InvokeModelWithResponseStream"
                        ],
                        "Resource": f"arn:aws:bedrock:{region}::foundation-model/*"
                    }
                ]
            })),
            tags={**tags, "Name": namer.resource("model-policy")})

        # Attach policy to model role
        factory.create("aws:iam:RolePolicyAttachment", f"{self.name}-model-policy-attachment",
            role=self.model_role.name,
            policy_arn=model_policy.arn)

        # Bedrock Agent
        self.agent = factory.create("aws:bedrock:Agent", f"{self.name}-agent",
            agent_name=agent_name,
            agent_resource_role_arn=self.agent_role.arn,
            foundation_model=model_id,
            instruction=system_prompt,
            tags={**tags, "Name": agent_name})

        # Exports
        pulumi.export("agent_id", self.agent.id if hasattr(self, 'agent') else None)
        pulumi.export("agent_name", self.agent.agent_name)
        pulumi.export("agent_arn", self.agent.agent_arn)
        pulumi.export("agent_role_arn", self.agent_role.arn)
        pulumi.export("model_role_arn", self.model_role.arn)
        pulumi.export("log_group_name", self.log_group.name)
        pulumi.export("model_id", model_id)

        pulumi.export('team_name', team_name)
        return self.get_outputs()

    def get_outputs(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent.id if hasattr(self, 'agent') else None,
            "agent_arn": self.agent.agent_arn,
            "agent_role_arn": self.agent_role.arn,
            "model_role_arn": self.model_role.arn,
            "log_group_name": self.log_group.name
        }

    @classmethod
    def get_metadata(cls) -> Dict[str, Any]:
        return {
            "name": "aws-bedrock-agent-nonprod",
            "title": "Bedrock AI Agent",
            "description": "Create an AWS Bedrock AgentCore Runtime agent for AI-powered applications",
            "category": "compute",
            "version": "1.0.0",
            "cloud": "aws",
            "environment": "nonprod",
            "base_cost": "~$50-150/month",
            "features": ["AI Agent Runtime", "Model Invocation", "CloudWatch Monitoring", "IAM Security"],
            "tags": ["ai", "bedrock", "agent", "llm"],
            "deployment_time": "3-5 minutes",
            "complexity": "intermediate",
            "pillars": [
                {"title": "Operational Excellence", "score": "good", "score_color": "#f59e0b", "description": "CloudWatch logging for agent observability", "practices": ["Centralized logging", "Monitoring dashboards", "Automated deployments"]},
                {"title": "Security", "score": "excellent", "score_color": "#10b981", "description": "Least privilege IAM roles with specific model permissions", "practices": ["Role-based access", "Resource-level permissions", "Service-linked roles"]},
                {"title": "Reliability", "score": "good", "score_color": "#f59e0b", "description": "Managed service with built-in redundancy", "practices": ["Managed infrastructure", "Error handling", "Retry mechanisms"]},
                {"title": "Performance Efficiency", "score": "excellent", "score_color": "#10b981", "description": "Optimized for AI workloads with serverless scaling", "practices": ["Serverless architecture", "Model optimization", "Caching strategies"]},
                {"title": "Cost Optimization", "score": "good", "score_color": "#f59e0b", "description": "Pay-per-use pricing model", "practices": ["Usage-based billing", "Resource tagging", "Cost monitoring"]},
                {"title": "Sustainability", "score": "good", "score_color": "#f59e0b", "description": "Efficient serverless compute with optimized models", "practices": ["Serverless efficiency", "Model optimization", "Resource sharing"]}
            ]
        }

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        return {
            "properties": {
                "project_name": {"type": "string", "default": "myapp"},
                "environment": {"type": "string", "default": "dev", "enum": ["dev", "staging", "prod"]},
                "region": {"type": "string", "default": "us-east-1"},
                "team": {"type": "string", "default": "platform"},
                "agent_name": {"type": "string", "description": "Name for the Bedrock agent"},
                "model_id": {"type": "string", "default": "anthropic.claude-sonnet-4-20250514", "description": "Bedrock foundation model ID"},
                "system_prompt": {"type": "string", "description": "System prompt for the agent (multiline)"}
            },
            "required": ["agent_name", "system_prompt"]
        }