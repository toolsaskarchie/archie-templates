from typing import Any, Dict, Optional, Union
from provisioner.templates.base.config import TemplateConfig

class IAMPolicyAtomicConfig(TemplateConfig):
    """Configuration for IAM Policy Atomic Template"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        
        # Get AWS-specific parameters
        aws_params = self.get_provider_config('aws')
        
        # Policy configuration
        self.policy_name: str = aws_params.get("policy_name") or aws_params.get("name", "iam-policy")
        self.description: str = aws_params.get("description", "Managed by Archie")
        self.path: str = aws_params.get("path", "/")
        
        # Policy document (can be dict or JSON string)
        self.policy: Union[str, Dict[str, Any]] = aws_params.get("policy", {})
        
        # Metadata
        self.project_name: str = aws_params.get("project_name", "archie")
        self.environment: str = aws_params.get("environment", "dev")
        self.region: str = aws_params.get("region", "us-east-1")
        
        # Tags
        self.tags: Dict[str, str] = aws_params.get("tags", {})
