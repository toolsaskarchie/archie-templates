"""
Archie Secret Template
Stores cloud credentials in AWS Secrets Manager for Archie's onboarding.
"""
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
    def get_metadata(cls):
        """Template metadata for marketplace registration"""
        from provisioner.templates.base.template import TemplateMetadata, TemplateCategory
        return TemplateMetadata(
            name="aws-archie-secret",
            title="Archie Credentials Secret",
            description="Securely stores AWS Access Keys in AWS Secrets Manager. Encrypted at rest and managed via Archie's standardized security patterns, providing a safe way to handle sensitive onboarding credentials.",
            category=TemplateCategory.SECURITY,
            version="1.0.0",
            author="InnovativeApps",
            tags=["iam", "secrets", "security", "aws", "onboarding"],
            features=[
                "Secure, encrypted credential storage",
                "Automated Secrets Manager lifecycle management",
                "Direct compatibility with Archie deployment engine",
                "VPC-integrated access control potential",
                "Compliance-ready secret management"
            ],
            estimated_cost="$0.40/month (per AWS pricing)",
            complexity="beginner",
            deployment_time="1-2 minutes",
            marketplace_group="SECURITY"
        )

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        """Get configuration schema for the UI"""
        return ArchieSecretConfig.get_config_schema()

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        """Get config schema for UI."""
        return ArchieSecretConfig.get_config_schema()

    @classmethod
    def get_metadata(cls):
        """Get template metadata."""
        from provisioner.templates.base.template import TemplateMetadata, TemplateCategory
        return TemplateMetadata(
            name="aws-archie-secret",
            title="Archie Onboarding Secret",
            description="Securely store your AWS Access Keys in AWS Secrets Manager for Archie's 'Secret' deployment method. Ideal for users who want to manage their own sensitive credentials while giving Archie safe access.",
            category=TemplateCategory.SECURITY,
            version="1.0.0",
            author="InnovativeApps",
            features=[
                "Secure credential storage (Secrets Manager)",
                "Principle of Least Privilege support",
                "Automated Secret ARN generation",
                "Directly compatible with Archie Onboarding",
                "Encrypted at rest by default"
            ],
            tags=["iam", "secrets", "security", "onboarding", "managed"],
            estimated_cost="$0.40/month (AWS Secrets Manager cost)",
            complexity="beginner",
            deployment_time="1-2 minutes",
            marketplace_group="aws-security-group",
            is_listed_in_marketplace=True
        )
