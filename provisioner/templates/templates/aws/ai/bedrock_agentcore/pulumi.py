"""
AWS Bedrock AgentCore Runtime Template

Deploys a managed AI agent using AWS Bedrock AgentCore with:
- IAM role for agent execution with Bedrock permissions
- AgentCore Runtime definition with configurable model and system prompt
- AgentCore Runtime Endpoint for invocation
- CloudWatch log group for observability

Estimated cost: ~$0/mo base (pay-per-invocation via Bedrock API)
"""
from typing import Any, Dict
import json as _json
import pulumi
import pulumi_aws as aws
import time as _time

def _wait_for_iam(arn):
    """Wait for IAM eventual consistency before using role ARN"""
    _time.sleep(30)
    return arn


from provisioner.templates.base import InfrastructureTemplate, template_registry
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory
from provisioner.utils.aws import ResourceNamer, get_standard_tags


@template_registry("aws-bedrock-agentcore")
class BedrockAgentCoreTemplate(InfrastructureTemplate):
    """
    Bedrock AgentCore Runtime

    Creates:
    - IAM role with Bedrock AgentCore + InvokeModel permissions
    - AgentCore Agent Runtime definition
    - AgentCore Runtime Endpoint
    - CloudWatch Log Group for agent logs
    """

    def __init__(self, name=None, config=None, **kwargs):
        raw_config = config or kwargs or {}
        if name is None:
            name = raw_config.get('project_name', 'bedrock-agent')
        super().__init__(name, raw_config)

    def create_infrastructure(self):
        params = self.config.get('parameters', {})
        def cfg(key, default=None):
            return self.config.get(key) or params.get(key) or default

        project = cfg('project_name', 'myagent')
        env = cfg('environment', 'dev')
        agent_name = cfg('agent_name', project)
        model_id = cfg('model_id', 'us.anthropic.claude-sonnet-4-20250514-v1:0')
        system_prompt = cfg('system_prompt', 'You are an Archie DevOps Agent — an AI infrastructure assistant that manages cloud stacks through the Archie platform. You can list stacks, check drift, view stack details, and browse blueprints. Be concise and flag any issues you find.')
        team_name = cfg('team_name', '')

        namer = ResourceNamer(project=project, environment=env, region='us-east-1', template='aws-bedrock-agentcore')
        tags = get_standard_tags(project=project, environment=env, template='bedrock-agentcore')
        tags['ManagedBy'] = 'Archie'
        if team_name:
            tags['Team'] = team_name

        # 1. IAM Role for Agent execution
        assume_role_policy = '''{
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
        }'''

        agent_role = factory.create(
            "aws:iam:Role",
            f"role-agentcore-{project}-{env}",
            assume_role_policy=assume_role_policy,
            tags={**tags, "Name": f"role-agentcore-{project}-{env}"},
        )

        # InvokeModel + Logs policy
        invoke_policy = factory.create(
            "aws:iam:RolePolicy",
            f"policy-agentcore-{project}-{env}",
            role=agent_role.name,
            policy=_json.dumps({
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": [
                            "bedrock:InvokeModel",
                            "bedrock:InvokeModelWithResponseStream",
                        ],
                        "Resource": f"arn:aws:bedrock:*::foundation-model/{model_id}"
                    },
                    {
                        "Effect": "Allow",
                        "Action": [
                            "logs:CreateLogGroup",
                            "logs:CreateLogStream",
                            "logs:PutLogEvents",
                        ],
                        "Resource": "arn:aws:logs:*:*:log-group:/aws/bedrock/*"
                    },
                    {
                        "Effect": "Allow",
                        "Action": [
                            "ecr:GetAuthorizationToken"
                        ],
                        "Resource": "*"
                    },
                    {
                        "Effect": "Allow",
                        "Action": [
                            "ecr:BatchGetImage",
                            "ecr:GetDownloadUrlForLayer"
                        ],
                        "Resource": "arn:aws:ecr:*:*:repository/*"
                    }
                ]
            }),
        )

        # 2. CloudWatch Log Group
        log_group = factory.create(
            "aws:cloudwatch:LogGroup",
            f"logs-agentcore-{project}-{env}",
            name=f"/aws/bedrock/agentcore/{project}-{env}",
            retention_in_days=14,
            tags={**tags, "Name": f"logs-agentcore-{project}-{env}"},
        )

        # 3. AgentCore Runtime — role_arn uses Output which ensures role exists first
        agent_runtime = aws.bedrock.AgentcoreAgentRuntime(
            f"agentcore-{project}-{env}",
            agent_runtime_name=f"{agent_name.replace('-', '_')}_{env}",
            role_arn=agent_role.arn.apply(_wait_for_iam),
            description=f"Bedrock AgentCore agent for {project} ({env})",
            agent_runtime_artifact={
                "container_configuration": {
                    "container_uri": cfg('container_uri', '416851285955.dkr.ecr.us-east-1.amazonaws.com/archie-agentcore-insurance:latest'),
                },
            },
            network_configuration={
                "network_mode": "PUBLIC",
            },
            environment_variables={
                "MODEL_ID": model_id,
                "SYSTEM_PROMPT": system_prompt,
                "ENVIRONMENT": env,
                "ARCHIE_API": "https://9eumbz9bog.execute-api.us-east-1.amazonaws.com",
                "ARCHIE_TOKEN": cfg('archie_token', ''),
            },
            tags={**tags, "Name": f"agentcore-{project}-{env}"},
            opts=pulumi.ResourceOptions(depends_on=[agent_role, invoke_policy]),
        )

        # 4. AgentCore Runtime Endpoint
        agent_endpoint = aws.bedrock.AgentcoreAgentRuntimeEndpoint(
            f"endpoint-{project}-{env}",
            agent_runtime_id=agent_runtime.agent_runtime_id,
            name=f"{agent_name.replace('-', '_')}_endpoint_{env}",
            description=f"Endpoint for {agent_name} ({env})",
            tags={**tags, "Name": f"endpoint-{project}-{env}"},
        )

        # Exports
        pulumi.export('agent_name', agent_name)
        pulumi.export('agent_runtime_id', agent_runtime.agent_runtime_id)
        pulumi.export('agent_runtime_arn', agent_runtime.agent_runtime_arn)
        pulumi.export('endpoint_id', agent_endpoint.id)
        pulumi.export('agent_role_arn', agent_role.arn)
        pulumi.export('log_group_name', log_group.name)
        pulumi.export('model_id', model_id)
        pulumi.export('environment', env)
        pulumi.export('team_name', team_name)

        return {}

    def get_outputs(self):
        return {}

    @classmethod
    def get_metadata(cls):
        return {
            'name': 'aws-bedrock-agentcore',
            'title': 'DevOps Agent (AgentCore)',
            'description': 'Deploy a managed AI agent using AWS Bedrock AgentCore with IAM roles, runtime endpoint, and CloudWatch observability.',
            'category': 'compute',
            'cloud': 'aws',
            'tier': 'standard',
            'estimated_cost': '~$0/mo base (pay-per-invocation)',
            'deployment_time': '2-3 minutes',
            'features': [
                'Managed AgentCore Runtime',
                'Configurable foundation model (Claude, Titan, etc.)',
                'Custom system prompt',
                'IAM least-privilege roles',
                'CloudWatch log group for observability',
                'Runtime endpoint for API invocation',
            ],
            'use_cases': [
                'AI-powered chatbots and assistants',
                'Document analysis agents',
                'Code review and generation agents',
                'Customer support automation',
            ],
            'pillars': [
                {'title': 'Security', 'description': 'Least-privilege IAM roles scoped to specific model ARN'},
                {'title': 'Operational Excellence', 'description': 'CloudWatch logs with 14-day retention for debugging'},
                {'title': 'Cost Optimization', 'description': 'Pay-per-invocation, no idle compute costs'},
            ],
        }
