"""AWS Secrets Manager Secret Atomic Configuration"""
from dataclasses import dataclass
from typing import Any, Dict, Optional

@dataclass
class SecretsManagerSecretAtomicConfig:
    secret_name: str
    description: Optional[str]
    secret_string: Optional[Any] # string or json-string
    project_name: str
    environment: str
    region: str
    kms_key_id: Optional[str] = None
    
    def __init__(self, config: Dict[str, Any]):
        aws_params = config.get('parameters', {}).get('aws', {})
        self.project_name = aws_params.get('project_name', 'default-project')
        self.environment = aws_params.get('environment', 'nonprod')
        self.region = aws_params.get('region', 'us-east-1')
        self.secret_name = aws_params.get('secret_name')
        self.description = aws_params.get('description', f"Secret for {self.project_name}")
        self.secret_string = aws_params.get('secret_string')
        self.kms_key_id = aws_params.get('kms_key_id')
        
        if not self.secret_name:
            # Fallback to name generation if not provided explicitly in parameters
            self.secret_name = f"archie/{self.project_name}/{self.environment}/credentials"
