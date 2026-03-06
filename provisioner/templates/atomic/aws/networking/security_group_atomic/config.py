"""
Configuration parser for Security Group Atomic Template
"""
from typing import Dict, Any, List, Optional
import pulumi


class SecurityGroupAtomicConfig:
    """Parsed and validated configuration for Security Group Atomic Template"""

    def __init__(self, raw_config: Dict[str, Any]):
        params = raw_config.get('parameters', {}).get('aws', {})

        # Core security group configuration
        self.security_group_name = params.get('security_group_name', params.get('securityGroupName', 'sg'))
        self.vpc_id = params.get('vpc_id', params.get('vpcId'))
        self.description = params.get('description', 'Security group created by Archie')
        
        # Ingress and egress rules
        self.ingress = params.get('ingress', [])
        self.egress = params.get('egress', [])
        
        # Metadata
        self.project_name = params.get('projectName', params.get('project_name', 'archie'))
        self.environment = params.get('environment', 'dev')
        self.region = params.get('region', 'us-east-1')
        self.tags = params.get('tags', {})
        
        # Validate required fields
        # Allow Pulumi Output objects (they'll be resolved at runtime)
        if not self.vpc_id and not isinstance(self.vpc_id, pulumi.Output):
            raise ValueError("vpc_id is required for Security Group Atomic template")
