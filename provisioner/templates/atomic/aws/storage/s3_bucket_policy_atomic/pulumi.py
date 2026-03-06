"""S3 Bucket Policy Template"""
from typing import Dict, Any
import pulumi
import pulumi_aws as aws

from provisioner.templates.atomic.base import AtomicTemplate
from .config import S3BucketPolicyAtomicConfig


class S3BucketPolicyAtomicTemplate(AtomicTemplate):
    """S3 Bucket Policy Template
    
    Creates S3 bucket policy directly.
    
    Creates:
        - aws.s3.BucketPolicy (actual AWS resource, visible in preview)
    
    Outputs:
        - bucket_id: S3 bucket ID
        - policy_id: Policy ID
    """
    
    def __init__(self, name: str, config: Dict[str, Any], **kwargs):
        """Initialize S3 bucket policy atomic template"""
        self.cfg = S3BucketPolicyAtomicConfig(**config)
        super().__init__(name, config, **kwargs)
        self.bucket_policy: aws.s3.BucketPolicy = None
    
    def create_infrastructure(self) -> Dict[str, Any]:
        """Create S3 bucket policy directly - shows as actual AWS resource in preview"""
        self.bucket_policy = aws.s3.BucketPolicy(
            f"{self.name}-bucket-policy",
            bucket=self.cfg.bucket_id,
            policy=self.cfg.policy,
            opts=self.resource_options
        )
        
        pulumi.export(f"{self.name}_bucket_id", self.bucket_policy.bucket)
        pulumi.export(f"{self.name}_policy_id", self.bucket_policy.id)
        
        return self.get_outputs()

    def get_metadata(self):
        """Get template metadata"""
        return {
            "name": "S3 Bucket Policy",
            "description": "Creates S3 bucket policy",
            "version": "1.0.0"
        }
    
    def get_outputs(self) -> Dict[str, Any]:
        """Get S3 bucket policy outputs"""
        if not self.bucket_policy:
            raise RuntimeError(f"S3 bucket policy {self.name} not created")
        
        return {
            "bucket_id": self.bucket_policy.bucket,
            "policy_id": self.bucket_policy.id,
        }
