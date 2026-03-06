"""
IAM Role Template
Creates a single IAM role resource - this is a true atomic resource.

Architecture: Layer 3 atomic that wraps Layer 2 component
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
from provisioner.templates.atomic.aws.iam.iam_role_atomic.config import IAMRoleAtomicConfig


@template_registry("aws-iam-role-atomic")
class IAMRoleAtomicTemplate(InfrastructureTemplate):
    """
    IAM Role Template
    
    Creates only an IAM role resource with:
    - Configurable assume role policy
    - Managed policy attachments
    - Inline policies
    - Tagging support
    
    This is a Layer 3 atomic.
    """
    
    def __init__(self, name: str = None, config: Dict[str, Any] = None, **kwargs):
        """Initialize template"""
        raw_config = config or kwargs or {}
        
        if name is None:
            name = raw_config.get('parameters', {}).get('aws', {}).get('role_name', 'iam-role')
        
        super().__init__(name, raw_config)
        self.cfg = IAMRoleAtomicConfig(raw_config)
        
        # Resources
        self.iam_role: Optional[aws.iam.Role] = None
    
    def create_infrastructure(self) -> Dict[str, Any]:
        """Create IAM role directly - shows as actual AWS resource in preview (Layer 2)"""
        tags = get_standard_tags(
            project=self.cfg.project_name,
            environment=self.cfg.environment,
            template="iam-role-atomic"
        )
        
        # Create IAM role using component (Layer 2)
        print(f"[IAMRole] Creating IAM role '{self.cfg.role_name}'")
        
        # Convert inline_policies from dict to list format with JSON string policy
        inline_policies_list = []
        if self.cfg.inline_policies:
            for policy_name, policy_doc in self.cfg.inline_policies.items():
                # Convert policy dict to JSON string
                policy_str = json.dumps(policy_doc) if isinstance(policy_doc, dict) else policy_doc
                inline_policies_list.append({
                    "name": policy_name,
                    "policy": policy_str
                })
        
        # Convert assume_role_policy to JSON string if it's a dict
        assume_role_policy_str = self.cfg.assume_role_policy
        if isinstance(assume_role_policy_str, dict):
            assume_role_policy_str = json.dumps(assume_role_policy_str)
        
        # Use pattern: aws.iam.Role(f"{self.name}-role", ...)
        self.iam_role = aws.iam.Role(
            self.name,
            name=self.cfg.role_name,
            assume_role_policy=assume_role_policy_str,
            managed_policy_arns=self.cfg.managed_policy_arns,
            inline_policies=inline_policies_list if inline_policies_list else None,
            tags=tags
        )
        
        # Export outputs
        pulumi.export("role_arn", self.iam_role.arn)
        pulumi.export("role_name", self.iam_role.name)
        
        print(f"[IAMRole] IAM role created successfully")
        
        return {
            "template_name": "iam-role-atomic",
            "outputs": {
                "role_arn": "Available after deployment",
                "role_name": self.cfg.role_name
            }
        }
    
    def get_outputs(self) -> Dict[str, Any]:
        """Get template outputs"""
        if not self.iam_role:
            return {
                "role_name": self.cfg.role_name,
                "status": "not_created"
            }
        
        return {
            "role_arn": self.iam_role.arn,
            "role_name": self.iam_role.name,
            "managed_policies_count": len(self.cfg.managed_policy_arns),
            "inline_policies_count": len(self.cfg.inline_policies)
        }
    
    @classmethod
    def get_metadata(cls) -> Dict[str, Any]:
        """Template metadata"""
        return {
            "name": "iam-role-atomic",
            "title": "IAM Role",
            "subtitle": "Single IAM role resource",
            "description": "Create a standalone IAM role with assume role policy, managed policies, and inline policies. This is an atomic resource containing only the IAM role itself.",
            "category": "iam",
            "provider": "aws",
            "tier": "atomic",
            "complexity": "simple",
            "icon": "🔑",
            "version": "1.0.0",
            "status": "stable",
            "estimated_cost": "$0/month",
            "deployment_time": "1 minute",
            "use_cases": [
                "Add IAM role to existing infrastructure",
                "Expert users building custom architectures",
                "Testing and learning IAM concepts"
            ],
            "features": [
                "Single IAM role resource",
                "Configurable assume role policy",
                "Managed policy attachments",
                "Inline policies",
                "Tagging support"
            ],
            "outputs": [
                "Role ARN",
                "Role name"
            ],
            "prerequisites": [],
            "tags": [
                "iam",
                "role",
                "atomic",
                "security"
            ]
        }
