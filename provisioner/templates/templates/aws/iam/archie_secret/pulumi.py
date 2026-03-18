"""
Archie Secret Template
Stores cloud credentials in AWS Secrets Manager for Archie's onboarding.
"""
from typing import Any, Dict, Optional
import pulumi
import json

# Import Archie utils for consistent patterns
from provisioner.utils.aws import (
    ResourceNamer,
    get_standard_tags
)
from provisioner.templates.base import template_registry, InfrastructureTemplate
from provisioner.templates.templates.aws.iam.archie_secret.config import ArchieSecretConfig
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory


@template_registry("aws-archie-secret")
class ArchieSecretTemplate(InfrastructureTemplate):
    """
    Archie Secret Template - Pattern B Implementation
    
    Creates:
    - AWS Secrets Manager secret
    - Secret version with credential data
    """
    
    def __init__(self, name: str = None, config: Dict[str, Any] = None, **kwargs):
        """Initialize Archie secret template"""
        raw_config = config or kwargs or {}
        self.cfg = ArchieSecretConfig(raw_config)
        
        if name is None:
            name = self.cfg.project_name
            
        super().__init__(name, raw_config)
        self.secret: Optional[aws.secretsmanager.Secret] = None
        self.secret_version: Optional[aws.secretsmanager.SecretVersion] = None

    def create_infrastructure(self) -> Dict[str, Any]:
        """Deploy infrastructure (implements abstract method)"""
        return self.create()

    def create(self) -> Dict[str, Any]:
        """Deploy Archie secret using factory pattern"""
        
        environment = self.cfg.environment or 'nonprod'
        
        # Tags
        tags = get_standard_tags(
            project=self.cfg.project_name,
            environment=environment,
            template="aws-archie-secret"
        )
        tags.update(self.cfg.tags)
        
        # Prepare secret data
        secret_data = {
            "access_key": self.cfg.access_key,
            "secret_key": self.cfg.secret_key
        }
        
        # 1. Create Secret
        self.secret = factory.create(
            "aws:secretsmanager:Secret",
            f"{self.name}-secret",
            name=self.cfg.secret_name,
            description=self.cfg.config_loader.get('secret.description'),
            tags=tags
        )
        
        # 2. Create Secret Version
        self.secret_version = factory.create(
            "aws:secretsmanager:SecretVersion",
            f"{self.name}-secret-version",
            secret_id=self.secret.id,
            secret_string=json.dumps(secret_data)
        )
        
        # Export outputs
        pulumi.export("secret_arn", self.secret.arn)
        pulumi.export("secret_name", self.secret.name)

        return self.get_outputs()

    def get_outputs(self) -> Dict[str, Any]:
        """Get template outputs"""
        if not self.secret:
            return {}
            
        return {
            "secret_arn": self.secret.arn,
            "secret_name": self.secret.name,
            "secret_id": self.secret.id
        }

    @classmethod
    def get_metadata(cls) -> Dict[str, Any]:
        """Template metadata for marketplace registration"""
        return {
            "name": "aws-archie-secret",
            "title": "Archie Credential Secret",
            "description": "Securely stores AWS Access Keys in AWS Secrets Manager. Encrypted at rest and managed via Archie's standardized security patterns, providing a safe way to handle sensitive onboarding credentials.",
            "category": "security",
            "version": "1.0.0",
            "author": "InnovativeApps",
            "cloud": "aws",
            "environment": "all",
            "base_cost": "$0.40/month",
            "tags": ["iam", "secrets", "security", "aws", "onboarding"],
            "features": [
                "Secure, encrypted credential storage",
                "Automated Secrets Manager lifecycle management",
                "Direct compatibility with Archie deployment engine",
                "VPC-integrated access control potential",
                "Compliance-ready secret management"
            ],
            "deployment_time": "1-2 minutes",
            "complexity": "low",
            "pillars": [
                {
                    "title": "Operational Excellence",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Automated secret provisioning with infrastructure as code",
                    "practices": [
                        "Infrastructure as Code for repeatable secret deployments",
                        "Automated secret version management via Pulumi",
                        "Standard tagging for governance and resource tracking",
                        "Consistent naming conventions for secret identification",
                        "One-click deployment eliminates manual Secrets Manager setup"
                    ]
                },
                {
                    "title": "Security",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "AWS-managed encryption with fine-grained access control",
                    "practices": [
                        "Secrets encrypted at rest using AWS KMS by default",
                        "IAM policies control who can access the secret",
                        "Secret versioning enables safe credential rotation",
                        "No plaintext credentials stored in code or config files",
                        "Audit trail via CloudTrail for all secret access events"
                    ]
                },
                {
                    "title": "Reliability",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Secrets Manager is a fully managed regional service",
                    "practices": [
                        "AWS-managed service with built-in high availability",
                        "Automatic replication within the region for durability",
                        "Secret versioning prevents accidental data loss",
                        "No infrastructure to maintain or monitor for uptime",
                        "Automated deployment reduces human error in configuration"
                    ]
                },
                {
                    "title": "Performance Efficiency",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Low-latency secret retrieval with caching support",
                    "practices": [
                        "Sub-millisecond secret retrieval via AWS SDK",
                        "Client-side caching eliminates repeated API calls",
                        "No compute resources required for secret management",
                        "Deploys in under 2 minutes with no warm-up required",
                        "Minimal API calls needed for credential access"
                    ]
                },
                {
                    "title": "Cost Optimization",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Minimal cost at $0.40/month per secret",
                    "practices": [
                        "Fixed $0.40/month per secret with no hidden charges",
                        "No compute or networking costs for secret storage",
                        "Eliminates need for self-managed credential vaults",
                        "API calls included in free tier for typical usage",
                        "Single secret stores multiple credential key-value pairs"
                    ]
                },
                {
                    "title": "Sustainability",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Fully managed service with zero idle resource consumption",
                    "practices": [
                        "No compute resources provisioned or running",
                        "Leverages shared AWS Secrets Manager infrastructure",
                        "Zero energy consumption beyond the managed service",
                        "Eliminates need for dedicated credential management servers",
                        "Serverless architecture minimizes environmental footprint"
                    ]
                }
            ]
        }

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        """Get configuration schema for the UI"""
        return ArchieSecretConfig.get_config_schema()
