"""
Configuration parser for IAM Instance Profile Atomic Template
"""
from typing import Dict, Any, Optional


class IAMInstanceProfileAtomicConfig:
    """Parsed and validated configuration for IAM Instance Profile Atomic Template"""

    def __init__(self, raw_config: Dict[str, Any]):
        params = raw_config.get('parameters', {}).get('aws', {})

        # Core IAM instance profile configuration
        self.profile_name = params.get('profile_name', params.get('profileName', 'instance-profile'))
        self.role_name = params.get('role_name', params.get('roleName'))
        
        # Metadata
        self.project_name = params.get('projectName', params.get('project_name', 'archie'))
        self.environment = params.get('environment', 'dev')
        self.region = params.get('region', 'us-east-1')
        self.tags = params.get('tags', {})
        
        # Validate required fields
        if not self.role_name:
            raise ValueError("role_name is required for IAM Instance Profile Atomic template")
