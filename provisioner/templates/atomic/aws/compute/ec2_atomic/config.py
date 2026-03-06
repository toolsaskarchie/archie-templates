"""
Configuration parser for EC2 Atomic Template
"""
from typing import Dict, Any, Optional, List


class EC2AtomicConfig:
    """Parsed and validated configuration for EC2 Atomic Template"""

    def __init__(self, raw_config: Dict[str, Any]):
        params = raw_config.get('parameters', {}).get('aws', {})

        # Core EC2 configuration
        self.instance_name = params.get('instance_name', params.get('instanceName', 'ec2-instance'))
        self.ami_id = params.get('ami_id', params.get('amiId'))
        self.instance_type = params.get('instance_type', params.get('instanceType', 't3.micro'))
        self.subnet_id = params.get('subnet_id', params.get('subnetId'))
        
        # Security and access
        self.security_group_ids = params.get('security_group_ids', params.get('securityGroupIds', []))
        self.key_name = params.get('key_name', params.get('keyName'))
        self.iam_instance_profile = params.get('iam_instance_profile', params.get('iamInstanceProfile'))
        
        # User data and configuration
        self.user_data = params.get('user_data', params.get('userData'))
        
        # Metadata
        self.project_name = params.get('projectName', params.get('project_name', 'archie-ec2'))
        self.environment = params.get('environment', 'dev')
        self.region = params.get('region', 'us-east-1')
        self.tags = params.get('tags', {})
        
        # Validate required fields
        if not self.ami_id:
            raise ValueError("ami_id is required for EC2 Atomic template")
        if not self.subnet_id:
            raise ValueError("subnet_id is required for EC2 Atomic template")
        if not self.security_group_ids:
            raise ValueError("security_group_ids is required for EC2 Atomic template")
