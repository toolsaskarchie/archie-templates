"""Configuration for AWS S3 Basic Bucket template."""
from typing import Dict, Any
from dataclasses import dataclass

@dataclass
class BasicBucketConfig:
    """Configuration for S3 Basic Bucket template"""
    
    bucketName: str
    projectName: str = "demo"
    region: str = "us-east-1"
    enableVersioning: bool = True
    lifecycleDays: int = 90
    
    def __init__(self, raw_config: Dict[str, Any]):
        """Parse configuration from user input"""
        self.bucketName = raw_config.get('bucketName')
        self.projectName = raw_config.get('projectName', 'demo')
        self.region = raw_config.get('region', 'us-east-1')
        self.enableVersioning = raw_config.get('enableVersioning', True)
        self.lifecycleDays = raw_config.get('lifecycleDays', 90)
        
        self._validate()
    
    def _validate(self):
        """Validate configuration"""
        if not self.bucketName:
            raise ValueError("bucketName is required")
        
        # Validate bucket name format
        if not self.bucketName.replace('-', '').replace('_', '').isalnum():
            raise ValueError("bucketName must contain only alphanumeric characters, hyphens, and underscores")