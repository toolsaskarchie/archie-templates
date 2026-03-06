"""
Security Group Template
Creates a single security group resource - this is a true atomic resource.

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
from provisioner.templates.atomic.aws.networking.security_group_atomic.config import SecurityGroupAtomicConfig


@template_registry("aws-security-group-atomic")
class SecurityGroupAtomicTemplate(InfrastructureTemplate):
    """
    Security Group Template
    
    Creates only a security group resource with:
    - Configurable ingress and egress rules
    - VPC association
    - Description and tagging
    
    This is a Layer 3 atomic - requires VPC to exist.
    """
    
    def __init__(self, name: str = None, config: Dict[str, Any] = None, **kwargs):
        """Initialize template"""
        raw_config = config or kwargs or {}
        
        if name is None:
            name = raw_config.get('parameters', {}).get('aws', {}).get('security_group_name', 'sg')
        
        super().__init__(name, raw_config)
        self.cfg = SecurityGroupAtomicConfig(raw_config)
        
        # Resources
        self.security_group: Optional[aws.ec2.SecurityGroup] = None
    
    def create_infrastructure(self) -> Dict[str, Any]:
        """Create security group directly - shows as actual AWS resource in preview (Layer 2)"""
        tags = get_standard_tags(
            project=self.cfg.project_name,
            environment=self.cfg.environment,
            template="security-group-atomic"
        )
        
        # Create security group using component (Layer 2)
        print(f"[SecurityGroup] Creating security group '{self.cfg.security_group_name}'")
        # Use pattern: aws.ec2.SecurityGroup(f"{self.name}-securitygroup", ...)
        self.security_group = aws.ec2.SecurityGroup(
            self.name,
            vpc_id=self.cfg.vpc_id,
            description=self.cfg.description,
            ingress=self.cfg.ingress,
            egress=self.cfg.egress,
            tags={**tags, "Name": self.cfg.security_group_name}
        )
        
        # Export outputs
        pulumi.export("security_group_id", self.security_group.id)
        pulumi.export("security_group_name", self.cfg.security_group_name)
        pulumi.export("vpc_id", self.cfg.vpc_id)
        
        print(f"[SecurityGroup] Security group created successfully")
        
        return {
            "template_name": "security-group-atomic",
            "outputs": {
                "security_group_id": "Available after deployment",
                "security_group_name": self.cfg.security_group_name
            }
        }
    
    def get_outputs(self) -> Dict[str, Any]:
        """Get template outputs"""
        if not self.security_group:
            return {
                "security_group_name": self.cfg.security_group_name,
                "status": "not_created"
            }
        
        return {
            "security_group_id": self.security_group.id,
            "security_group_name": self.cfg.security_group_name,
            "vpc_id": self.cfg.vpc_id,
            "ingress_rules": len(self.cfg.ingress),
            "egress_rules": len(self.cfg.egress)
        }
    
    @classmethod
    def get_metadata(cls) -> Dict[str, Any]:
        """Template metadata"""
        return {
            "name": "security-group-atomic",
            "title": "Security Group",
            "subtitle": "Single security group resource",
            "description": "Create a standalone security group with configurable ingress and egress rules. This is an atomic resource containing only the security group itself - requires existing VPC.",
            "category": "networking",
            "provider": "aws",
            "tier": "atomic",
            "complexity": "simple",
            "icon": "🛡️",
            "version": "1.0.0",
            "status": "stable",
            "estimated_cost": "$0/month",
            "deployment_time": "1 minute",
            "use_cases": [
                "Add security group to existing infrastructure",
                "Expert users building custom architectures",
                "Testing and learning security group concepts"
            ],
            "features": [
                "Single security group resource",
                "Configurable ingress rules",
                "Configurable egress rules",
                "VPC association",
                "Tagging support"
            ],
            "outputs": [
                "Security group ID",
                "Security group name",
                "VPC ID"
            ],
            "prerequisites": [
                "VPC must exist"
            ],
            "tags": [
                "security-group",
                "networking",
                "atomic",
                "firewall"
            ]
        }
