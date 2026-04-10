"""
AWS Bedrock Full Agent Stack Template

Complete AI agent infrastructure with:
- AgentCore Runtime with custom container support
- AgentCore Memory for conversation persistence
- AgentCore Gateway with MCP tool access
- ECR Repository for agent container images
- IAM roles with least-privilege permissions
- CloudWatch observability

Estimated cost: ~$5-20/mo base + per-invocation
"""
from typing import Any, Dict
import json as _json
import pulumi
import pulumi_aws as aws
import time as _time

def _wait_for_iam(arn):
    """Wait for IAM eventual consistency before using role ARN"""
    _time.sleep(60)
    return arn


from provisioner.templates.base import InfrastructureTemplate, template_registry
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory
from provisioner.utils.aws import ResourceNamer, get_standard_tags


@template_registry("aws-bedrock-agent-stack")
class BedrockAgentStackTemplate(InfrastructureTemplate):
    """
    Full Bedrock Agent Stack

    Creates:
    - ECR Repository for agent container images
    - IAM role with Bedrock + ECR + Logs permissions
    - AgentCore Agent Runtime
    - AgentCore Runtime Endpoint
    - AgentCore Memory for conversation persistence
    - AgentCore Code Interpreter (optional)
    - CloudWatch Log Group
    """

    def __init__(self, name=None, config=None, **kwargs):
        raw_config = config or kwargs or {}
        if name is None:
            name = raw_config.get('project_name', 'agent-stack')
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
        enable_memory = cfg('enable_memory', True)
        enable_code_interpreter = cfg('enable_code_interpreter', False)

        safe_name = agent_name.replace('-', '_').replace(' ', '_')
        namer = ResourceNamer(project=project, environment=env, region='us-east-1', template='aws-bedrock-agent-stack')
        tags = get_standard_tags(project=project, environment=env, template='bedrock-agent-stack')
        tags['ManagedBy'] = 'Archie'
        if team_name:
            tags['Team'] = team_name

        # 1. ECR Repository — store agent container images
        ecr_repo = factory.create(
            "aws:ecr:Repository",
            f"ecr-{project}-agent-{env}",
            name=f"{project}-agent-{env}",
            image_tag_mutability="MUTABLE",
            image_scanning_configuration={"scan_on_push": True},
            tags={**tags, "Name": f"ecr-{project}-agent-{env}"},
        )

        # 2. IAM Role for Agent execution
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
            f"role-agent-{project}-{env}",
            assume_role_policy=assume_role_policy,
            tags={**tags, "Name": f"role-agent-{project}-{env}"},
        )

        # Comprehensive policy: InvokeModel + ECR pull + Logs + Memory
        agent_managed_policy = aws.iam.Policy(
            f"policy-agent-{project}-{env}",
            policy=_json.dumps({
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": [
                            "bedrock:InvokeModel",
                            "bedrock:InvokeModelWithResponseStream",
                        ],
                        "Resource": ["arn:aws:bedrock:*::foundation-model/*", "arn:aws:bedrock:*:*:inference-profile/*"]
                    },
                    {
                        "Effect": "Allow",
                        "Action": [
                            "ecr:GetDownloadUrlForLayer",
                            "ecr:BatchGetImage",
                        ],
                        "Resource": "arn:aws:ecr:*:*:repository/*"
                    },
                    {
                        "Effect": "Allow",
                        "Action": [
                            "ecr:GetAuthorizationToken",
                        ],
                        "Resource": "*"
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
                            "ecr:GetAuthorizationToken",
                        ],
                        "Resource": "*"
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
        )

        # Attach policy to role
        agent_policy = aws.iam.RolePolicyAttachment(
            f"attach-agent-{project}-{env}",
            role=agent_role.name,
            policy_arn=agent_managed_policy.arn,
        )

        # 3. CloudWatch Log Group
        log_group = factory.create(
            "aws:cloudwatch:LogGroup",
            f"logs-agent-{project}-{env}",
            name=f"/aws/bedrock/agent/{project}-{env}",
            retention_in_days=14,
            tags={**tags, "Name": f"logs-agent-{project}-{env}"},
        )

        # 4. Wait for IAM policy to propagate to ECR service
        print('[AGENTCORE] Waiting 60s for IAM propagation...')
        _time.sleep(60)

        # AgentCore Runtime
        container_uri = cfg('container_uri', '416851285955.dkr.ecr.us-east-1.amazonaws.com/archie-agentcore-insurance:latest')

        agent_runtime = aws.bedrock.AgentcoreAgentRuntime(
            f"runtime-{project}-{env}",
            agent_runtime_name=f"{safe_name}_{env}",
            role_arn=agent_role.arn,
            description=f"Bedrock Agent for {project} ({env}) — {model_id}",
            agent_runtime_artifact={
                "container_configuration": {
                    "container_uri": container_uri,
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
                "PROJECT": project,
            },
            tags={**tags, "Name": f"runtime-{project}-{env}"},
            opts=pulumi.ResourceOptions(depends_on=[agent_role, agent_policy]),
        )

        # 5. AgentCore Runtime Endpoint
        agent_endpoint = aws.bedrock.AgentcoreAgentRuntimeEndpoint(
            f"endpoint-{project}-{env}",
            agent_runtime_id=agent_runtime.agent_runtime_id,
            name=f"{safe_name}_endpoint_{env}",
            description=f"Endpoint for {agent_name} ({env})",
            tags={**tags, "Name": f"endpoint-{project}-{env}"},
        )

        # 6. AgentCore Memory (optional — conversation persistence)
        if enable_memory:
            agent_memory = aws.bedrock.AgentcoreMemory(
                f"memory-{project}-{env}",
                event_expiry_duration=30,  # days (7-365)
                name=f"{safe_name}_memory_{env}",
                tags={**tags, "Name": f"memory-{project}-{env}"},
            )
            pulumi.export('memory_id', agent_memory.id)

        # 7. AgentCore Code Interpreter (optional — lets agent run code)
        if enable_code_interpreter:
            code_interpreter = aws.bedrock.AgentcoreCodeInterpreter(
                f"codeinterp-{project}-{env}",
                name=f"{safe_name}_codeinterp_{env}",
                tags={**tags, "Name": f"codeinterp-{project}-{env}"},
            )
            pulumi.export('code_interpreter_id', code_interpreter.id)

        # Exports
        pulumi.export('agent_name', agent_name)
        pulumi.export('model_id', model_id)
        pulumi.export('agent_runtime_id', agent_runtime.agent_runtime_id)
        pulumi.export('agent_runtime_arn', agent_runtime.agent_runtime_arn)
        pulumi.export('endpoint_id', agent_endpoint.id)
        pulumi.export('ecr_repository_url', ecr_repo.repository_url)
        pulumi.export('agent_role_arn', agent_role.arn)
        pulumi.export('log_group_name', log_group.name)
        pulumi.export('environment', env)
        pulumi.export('team_name', team_name)

        return {}

    def get_outputs(self):
        return {}

    @classmethod
    def get_metadata(cls):
        return {
            'name': 'aws-bedrock-agent-stack',
            'title': 'DevOps Agent Stack',
            'description': 'Complete AI agent infrastructure: AgentCore Runtime, Memory, Code Interpreter, ECR for custom containers, IAM, and CloudWatch.',
            'category': 'compute',
            'cloud': 'aws',
            'tier': 'standard',
            'estimated_cost': '~$5-20/mo base + per-invocation',
            'deployment_time': '3-5 minutes',
            'features': [
                'AgentCore Runtime with custom container support',
                'ECR Repository for Strands agent images',
                'Conversation memory persistence',
                'Optional Code Interpreter for dynamic code execution',
                'IAM least-privilege with ECR pull + Bedrock invoke',
                'CloudWatch logs for observability',
                'Configurable foundation model',
            ],
            'use_cases': [
                'Production AI agent deployment',
                'Strands SDK agent hosting',
                'Multi-tool agent with MCP gateway',
                'Code-executing research agents',
                'Customer support with conversation memory',
            ],
            'pillars': [
                {'title': 'Security', 'description': 'Least-privilege IAM, ECR image scanning, scoped model access'},
                {'title': 'Operational Excellence', 'description': 'CloudWatch logs, memory persistence, endpoint health'},
                {'title': 'Cost Optimization', 'description': 'Pay-per-invocation, optional components toggle on/off'},
                {'title': 'Reliability', 'description': 'AWS-managed runtime, auto-scaling, public endpoint'},
            ],
        }
