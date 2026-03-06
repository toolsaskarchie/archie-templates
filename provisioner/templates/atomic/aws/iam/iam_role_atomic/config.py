"""
Configuration parser for IAM Role Atomic Template
"""
from typing import Dict, Any, List, Optional
from provisioner.templates.base.config import TemplateConfig


class IAMRoleAtomicConfig(TemplateConfig):
    """Parsed and validated configuration for IAM Role Atomic Template"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        
        # Get AWS-specific parameters
        aws_params = self.get_provider_config('aws')

        # Core IAM role configuration
        self.role_name = aws_params.get('role_name', aws_params.get('roleName', 'iam-role'))
        self.assume_role_policy = aws_params.get('assume_role_policy', aws_params.get('assumeRolePolicy', {}))
        
        # Policies
        self.managed_policy_arns = aws_params.get('managed_policy_arns', aws_params.get('managedPolicyArns', []))
        self.inline_policies = aws_params.get('inline_policies', aws_params.get('inlinePolicies', {}))
        
        # Metadata
        self.project_name = aws_params.get('projectName', aws_params.get('project_name', 'archie'))
        self.environment = aws_params.get('environment', 'dev')
        self.region = aws_params.get('region', 'us-east-1')
        self.tags = aws_params.get('tags', {})
        
        # Validate required fields
        if not self.assume_role_policy:
            raise ValueError("assume_role_policy is required for IAM Role Atomic template")
