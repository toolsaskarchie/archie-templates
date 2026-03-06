"""
IAM Instance Profile Template
Creates a single IAM instance profile resource - this is a true atomic resource.

Architecture: Layer 3 atomic that wraps Layer 2 component
"""
from typing import Any, Dict, Optional
import pulumi
import pulumi_aws as aws

from provisioner.templates.base import (
    InfrastructureTemplate,
    template_registry
)
from provisioner.utils.aws import get_standard_tags
from provisioner.templates.atomic.aws.iam.iam_instance_profile_atomic.config import IAMInstanceProfileAtomicConfig


@template_registry("aws-iam-instance-profile-atomic")
class IAMInstanceProfileAtomicTemplate(InfrastructureTemplate):
    """
    IAM Instance Profile Template
    
    Creates only an IAM instance profile resource with:
    - Association with an existing IAM role
    - Tagging support
    
    This is a Layer 3 atomic - requires IAM role to exist.
    """
    
    def __init__(self, name: str = None, config: Dict[str, Any] = None, **kwargs):
        """Initialize template"""
        raw_config = config or kwargs or {}
        
        if name is None:
            name = raw_config.get('parameters', {}).get('aws', {}).get('profile_name', 'instance-profile')
        
        super().__init__(name, raw_config)
        self.cfg = IAMInstanceProfileAtomicConfig(raw_config)
        
        # Resources
        self.instance_profile: Optional[aws.iam.InstanceProfile] = None
    
    def create_infrastructure(self) -> Dict[str, Any]:
        """Create IAM instance profile directly - shows as actual AWS resource in preview (Layer 2)"""
        tags = get_standard_tags(
            project=self.cfg.project_name,
            environment=self.cfg.environment,
            template="iam-instance-profile-atomic"
        )
        
        # Create IAM instance profile using component (Layer 2)
        print(f"[IAMInstanceProfile] Creating IAM instance profile '{self.cfg.profile_name}'")
        # Use pattern: aws.iam.InstanceProfile(f"{self.name}-instanceprofile", ...)
        self.instance_profile = aws.iam.InstanceProfile(
            self.name,
            name=self.cfg.profile_name,
            role=self.cfg.role_name,
            tags=tags
        )
        
        # Export outputs
        pulumi.export("instance_profile_arn", self.instance_profile.arn)
        pulumi.export("instance_profile_name", self.instance_profile.name)
        pulumi.export("role_name", self.cfg.role_name)
        
        print(f"[IAMInstanceProfile] IAM instance profile created successfully")
        
        return {
            "template_name": "iam-instance-profile-atomic",
            "outputs": {
                "instance_profile_arn": "Available after deployment",
                "instance_profile_name": self.cfg.profile_name
            }
        }
    
    def get_outputs(self) -> Dict[str, Any]:
        """Get template outputs"""
        if not self.instance_profile:
            return {
                "profile_name": self.cfg.profile_name,
                "status": "not_created"
            }
        
        return {
            "instance_profile_arn": self.instance_profile.arn,
            "instance_profile_name": self.instance_profile.name,
            "role_name": self.cfg.role_name
        }
    
    @classmethod
    def get_metadata(cls) -> Dict[str, Any]:
        """Template metadata"""
        return {
            "name": "iam-instance-profile-atomic",
            "title": "IAM Instance Profile",
            "subtitle": "Single IAM instance profile resource",
            "description": "Create a standalone IAM instance profile associated with an existing IAM role. This is an atomic resource containing only the instance profile itself.",
            "category": "iam",
            "provider": "aws",
            "tier": "atomic",
            "complexity": "simple",
            "icon": "🎫",
            "version": "1.0.0",
            "status": "stable",
            "estimated_cost": "$0/month",
            "deployment_time": "1 minute",
            "use_cases": [
                "Add instance profile to existing infrastructure",
                "Expert users building custom architectures",
                "Testing and learning IAM concepts"
            ],
            "features": [
                "Single IAM instance profile resource",
                "IAM role association",
                "Tagging support"
            ],
            "outputs": [
                "Instance profile ARN",
                "Instance profile name",
                "Associated role name"
            ],
            "prerequisites": [
                "IAM role must exist"
            ],
            "tags": [
                "iam",
                "instance-profile",
                "atomic",
                "security"
            ]
        }
