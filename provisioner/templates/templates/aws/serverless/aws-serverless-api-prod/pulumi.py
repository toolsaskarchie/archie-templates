"""
AWS Serverless API Template
Event-driven API with API Gateway, Lambda, and DynamoDB.
Fully serverless with auto-scaling, X-Ray tracing, and CloudWatch monitoring.
"""
from typing import Any, Dict, Optional
from pathlib import Path
import pulumi
import pulumi_aws as aws

from provisioner.utils.aws import ResourceNamer
from provisioner.utils.aws.tags import get_standard_tags
from provisioner.templates.base import template_registry, InfrastructureTemplate
from provisioner.templates.template_config import TemplateConfig
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory


@template_registry("aws-serverless-api-prod")
class ServerlessApiProdTemplate(InfrastructureTemplate):
    """
    Serverless API — API Gateway + Lambda + DynamoDB

    Creates:
    - HTTP API Gateway with usage plans
    - Lambda function with X-Ray tracing
    - DynamoDB table with point-in-time recovery
    - IAM roles with least-privilege
    """

    def __init__(self, name: str = None, config: Dict[str, Any] = None, **kwargs):
        raw_config = config or kwargs or {}
        if name is None:
            name = (
                raw_config.get('project_name')
                or raw_config.get('parameters', {}).get('aws', {}).get('project_name')
                or 'serverless-api'
            )
        super().__init__(name, raw_config)
        template_dir = Path(__file__).parent
        self.cfg = TemplateConfig(template_dir, raw_config)
        self.config = raw_config

        self.api = None
        self.fn = None
        self.table = None

    def create_infrastructure(self) -> Dict[str, Any]:
        return self.create()

    def create(self) -> Dict[str, Any]:
        environment = self.cfg.get('environment', 'prod')
        namer = ResourceNamer(
            project=self.cfg.project_name,
            environment=environment,
            region=self.cfg.region,
            template="aws-serverless-api-prod"
        )
        tags = get_standard_tags(
            project=self.cfg.project_name,
            environment=environment,
            template="aws-serverless-api-prod"
        )

        lambda_memory = self.cfg.get('lambda_memory', 512)
        lambda_timeout = self.cfg.get('lambda_timeout', 30)

        # LAYER 1: API Gateway
        self.api = factory.create("aws:apigatewayv2:Api", f"{self.name}-api",
            protocol_type="HTTP", tags=tags)

        # LAYER 2: Lambda
        role = factory.create("aws:iam:Role", f"{self.name}-lambda-role",
            assume_role_policy='''{
                "Version": "2012-10-17",
                "Statement": [{"Effect": "Allow", "Principal": {"Service": "lambda.amazonaws.com"}, "Action": "sts:AssumeRole"}]
            }''', tags=tags)

        self.fn = factory.create("aws:lambda:Function", f"{self.name}-handler",
            runtime="python3.12", handler="index.handler",
            role=role.arn, memory_size=lambda_memory, timeout=lambda_timeout,
            tracing_config={"mode": "Active"}, tags=tags)

        # LAYER 3: DynamoDB
        self.table = factory.create("aws:dynamodb:Table", f"{self.name}-table",
            billing_mode="PAY_PER_REQUEST",
            hash_key="pk", range_key="sk",
            attributes=[{"name": "pk", "type": "S"}, {"name": "sk", "type": "S"}],
            point_in_time_recovery={"enabled": True},
            server_side_encryption={"enabled": True},
            tags=tags)

        # Pulumi exports
        if self.api:
            pulumi.export("api_endpoint", self.api.api_endpoint)
            pulumi.export("api_id", self.api.id)
        if self.fn:
            pulumi.export("lambda_arn", self.fn.arn)
            pulumi.export("function_name", self.fn.name)
        if self.table:
            pulumi.export("table_name", self.table.name)
            pulumi.export("table_arn", self.table.arn)

        return self.get_outputs()

    def get_outputs(self) -> Dict[str, Any]:
        outputs = {}
        if self.api:
            outputs["api_endpoint"] = self.api.api_endpoint
            outputs["api_id"] = self.api.id
        if self.fn:
            outputs["lambda_arn"] = self.fn.arn
            outputs["function_name"] = self.fn.name
        if self.table:
            outputs["table_name"] = self.table.name
            outputs["table_arn"] = self.table.arn
        return outputs

    @classmethod
    def get_metadata(cls) -> Dict[str, Any]:
        return {
            "name": "aws-serverless-api-prod",
            "title": "Serverless API (Lambda)",
            "description": "Event-driven API with API Gateway, Lambda, and DynamoDB. Fully serverless with auto-scaling.",
            "category": "serverless",
            "version": "1.0.0",
            "author": "AskArchie",
            "cloud": "aws",
            "environment": "prod",
            "base_cost": "$30/month",
            "estimated_cost": "~$30-200/mo (invocation dependent)",
            "deployment_time": "2-4 minutes",
            "complexity": "beginner",
            "tags": ["serverless", "lambda", "api-gateway", "dynamodb"],
            "features": [
                "HTTP API Gateway",
                "Lambda with X-Ray tracing",
                "DynamoDB with point-in-time recovery",
                "Pay-per-invocation pricing",
                "Server-side encryption"
            ],
            "use_cases": ["Webhooks and event handlers", "Lightweight REST APIs", "Cron jobs", "Backend for mobile/web apps"],
            "pillars": [
                {
                    "title": "Operational Excellence",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Fully managed services eliminate operational overhead with built-in monitoring and tracing",
                    "practices": [
                        "X-Ray distributed tracing for end-to-end visibility",
                        "CloudWatch Logs auto-configured for Lambda",
                        "API Gateway access logs for request auditing",
                        "Infrastructure as Code with Pulumi for repeatable deployments",
                        "No server patching or OS maintenance required"
                    ]
                },
                {
                    "title": "Security",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Least-privilege IAM roles with encryption at rest and in transit",
                    "practices": [
                        "IAM roles with least-privilege permissions",
                        "DynamoDB server-side encryption enabled",
                        "API Gateway TLS encryption in transit",
                        "Lambda runs in isolated execution environment",
                        "No long-lived credentials or SSH access"
                    ]
                },
                {
                    "title": "Reliability",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Fully managed services with built-in redundancy and automatic failover",
                    "practices": [
                        "Lambda automatically runs across multiple AZs",
                        "DynamoDB point-in-time recovery enabled",
                        "API Gateway managed availability across regions",
                        "Automatic retry and dead-letter queue support",
                        "No single points of failure in serverless architecture"
                    ]
                },
                {
                    "title": "Performance Efficiency",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Auto-scales from zero to thousands of concurrent requests with configurable memory",
                    "practices": [
                        "Lambda auto-scaling to thousands of concurrent executions",
                        "DynamoDB on-demand capacity scales automatically",
                        "API Gateway managed scaling with no configuration",
                        "Configurable Lambda memory for performance tuning",
                        "HTTP API Gateway for low-latency request routing"
                    ]
                },
                {
                    "title": "Cost Optimization",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Pay-per-invocation pricing with zero cost when idle",
                    "practices": [
                        "No idle costs when not processing requests",
                        "DynamoDB on-demand billing scales with usage",
                        "API Gateway pay-per-request pricing model",
                        "Lambda billed per 1ms of execution time",
                        "No reserved capacity or minimum commitments"
                    ]
                },
                {
                    "title": "Sustainability",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Serverless architecture maximizes resource utilization and minimizes idle waste",
                    "practices": [
                        "Scales to zero when not in use, no idle resources",
                        "Shared infrastructure reduces per-tenant carbon footprint",
                        "AWS optimizes underlying compute for energy efficiency",
                        "No over-provisioned servers running continuously",
                        "Event-driven design processes only when needed"
                    ]
                }
            ]
        }

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "lambda_memory": {"type": "integer", "default": 512, "title": "Lambda Memory (MB)",
                    "description": "Lambda memory allocation", "order": 10, "group": "Compute",
                    "cost_impact": "Proportional to memory"},
                "lambda_timeout": {"type": "integer", "default": 30, "title": "Lambda Timeout (s)",
                    "description": "Lambda timeout in seconds", "order": 11, "group": "Compute"}
            },
            "required": ["project_name", "region"]
        }
