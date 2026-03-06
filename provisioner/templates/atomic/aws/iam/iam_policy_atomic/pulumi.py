"""
IAM Policy Template
Creates a standalone IAM policy resource.
"""
from typing import Any, Dict, Optional
import json
import pulumi
import pulumi_aws as aws

from provisioner.templates.base import (
    InfrastructureTemplate,
    template_registry
)
from provisioner.utils.aws import get_standard_tags
from .config import IAMPolicyAtomicConfig


@template_registry("aws-iam-policy-atomic")
class IAMPolicyAtomicTemplate(InfrastructureTemplate):
    """
    IAM Policy Template
    
    Creates a standalone IAM policy resource.
    This is a Layer 3 atomic.
    """
    
    def __init__(self, name: str = None, config: Dict[str, Any] = None, **kwargs):
        """Initialize template"""
        raw_config = config or kwargs or {}
        
        if name is None:
            name = raw_config.get('parameters', {}).get('aws', {}).get('policy_name', 'iam-policy')
        
        super().__init__(name, raw_config)
        self.cfg = IAMPolicyAtomicConfig(raw_config)
        
        # Resources
        self.policy: Optional[aws.iam.Policy] = None
    
    def create_infrastructure(self) -> Dict[str, Any]:
        """Create IAM policy directly"""
        tags = get_standard_tags(
            project=self.cfg.project_name,
            environment=self.cfg.environment,
            template="iam-policy-atomic"
        )
        # Merge custom tags
        tags.update(self.cfg.tags)
        
        print(f"[IAMPolicy] Creating IAM policy '{self.cfg.policy_name}'")
        
        # Convert policy to JSON string if it's a dict
        policy_doc = self.cfg.policy
        if isinstance(policy_doc, dict) and policy_doc:
            policy_doc = json.dumps(policy_doc)
        
        # Create IAM policy
        self.policy = aws.iam.Policy(
            self.name,
            name=self.cfg.policy_name,
            description=self.cfg.description,
            path=self.cfg.path,
            policy=policy_doc,
            tags=tags
        )
        
        # Export outputs
        pulumi.export("policy_arn", self.policy.arn)
        pulumi.export("policy_name", self.policy.name)
        
        print(f"[IAMPolicy] IAM policy created successfully")
        
        return {
            "template_name": "iam-policy-atomic",
            "outputs": {
                "policy_arn": self.policy.arn,
                "policy_name": self.policy.name
            }
        }
    
    def get_outputs(self) -> Dict[str, Any]:
        """Get template outputs"""
        if not self.policy:
            return {
                "policy_name": self.cfg.policy_name,
                "status": "not_created"
            }
        
        return {
            "policy_arn": self.policy.arn,
            "policy_name": self.policy.name,
            "policy_id": self.policy.id
        }
    
    @classmethod
    def get_metadata(cls) -> Dict[str, Any]:
        """Template metadata"""
        return {
            "name": "iam-policy-atomic",
            "title": "IAM Policy",
            "subtitle": "Standalone IAM policy",
            "description": "Create a standalone IAM policy resource.",
            "category": "iam",
            "provider": "aws",
            "tier": "atomic",
            "complexity": "simple",
            "icon": "📜",
            "version": "1.0.0",
            "status": "stable",
            "estimated_cost": "$0/month",
            "deployment_time": "1 minute",
            "use_cases": [
                "Create custom permissions",
                "Attach to IAM roles or users"
            ],
            "features": [
                "Single IAM policy resource",
                "Configurable JSON document",
                "Tagging support"
            ],
            "outputs": [
                "Policy ARN",
                "Policy name"
            ],
            "prerequisites": [],
            "tags": [
                "iam",
                "policy",
                "atomic",
                "security"
            ]
        }
