"""AWS Secrets Manager Secret Template"""
from typing import Any, Dict, Optional
import pulumi
import pulumi_aws as aws

from provisioner.templates.base import InfrastructureTemplate, template_registry
from provisioner.utils.aws import get_standard_tags
from .config import SecretsManagerSecretAtomicConfig

@template_registry("aws-secretsmanager-secret-atomic")
class SecretsManagerSecretAtomicTemplate(InfrastructureTemplate):
    """Atomic Secrets Manager Secret Template"""
    
    def __init__(self, name: str = None, config: Dict[str, Any] = None, **kwargs):
        """Initialize template"""
        raw_config = config or kwargs or {}
        
        # Determine name for Pulumi resource
        if name is None:
            name = raw_config.get('parameters', {}).get('aws', {}).get('secret_name', 'archie-secret')
            
        super().__init__(name, raw_config)
        self.cfg = SecretsManagerSecretAtomicConfig(raw_config)
        
        # Resources for access
        self.secret: Optional[aws.secretsmanager.Secret] = None
        self.version: Optional[aws.secretsmanager.SecretVersion] = None

    def create_infrastructure(self) -> Dict[str, Any]:
        """Create Secrets Manager Secret directly"""
        tags = get_standard_tags(
            project=self.cfg.project_name,
            environment=self.cfg.environment,
            template="secretsmanager-secret-atomic"
        )
        
        print(f"[SecretsManager] Creating Secret '{self.cfg.secret_name}'")
        
        # Create Secret metadata
        self.secret = aws.secretsmanager.Secret(
            self.name,
            name=self.cfg.secret_name,
            description=self.cfg.description,
            kms_key_id=self.cfg.kms_key_id,
            recovery_window_in_days=0, # Force delete for now in sandbox/testing
            tags=tags
        )
        
        # Create Secret Value if string provided
        if self.cfg.secret_string:
            self.version = aws.secretsmanager.SecretVersion(
                f"{self.name}-version",
                secret_id=self.secret.id,
                secret_string=self.cfg.secret_string
            )
            
        # Export outputs to Pulumi state
        pulumi.export("secret_arn", self.secret.arn)
        pulumi.export("secret_name", self.secret.name)
        
        print(f"[SecretsManager] Secret created successfully")
        
        return {
            "template_name": "secretsmanager-secret-atomic",
            "outputs": {
                "secret_arn": self.secret.arn,
                "secret_name": self.secret.name
            }
        }

    def get_outputs(self) -> Dict[str, Any]:
        """Get template outputs"""
        if not self.secret:
            return {"status": "not_created"}
            
        return {
            "secret_arn": self.secret.arn,
            "secret_name": self.secret.name
        }

    @classmethod
    def get_metadata(cls) -> Dict[str, Any]:
        """Atomic metadata"""
        return {
            "name": "secretsmanager-secret-atomic",
            "title": "Secrets Manager Secret",
            "subtitle": "Single Secrets Manager secret",
            "description": "Create a standalone AWS Secrets Manager secret. resource for secure credential storage.",
            "category": "security",
            "provider": "aws",
            "tier": "atomic",
            "complexity": "simple",
            "icon": "🔒",
            "version": "1.0.0",
            "status": "stable",
            "estimated_cost": "$0.40/month",
            "deployment_time": "1 minute",
            "features": [
                "Secrets Manager Secret resource",
                "Optional initial secret version",
                "KMS integration",
                "Tagging support"
            ],
            "outputs": [
                "Secret ARN",
                "Secret Name"
            ],
            "tags": ["security", "secrets", "atomic"]
        }
