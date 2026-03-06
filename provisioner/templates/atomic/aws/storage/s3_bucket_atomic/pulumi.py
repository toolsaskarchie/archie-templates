"""S3 Bucket Template - Creates S3 Bucket"""
from typing import Dict, Any
import pulumi
import pulumi_aws as aws

from provisioner.templates.atomic.base import AtomicTemplate
from .config import S3BucketAtomicConfig


class S3BucketAtomicTemplate(AtomicTemplate):
    """S3 Bucket Template
    
    Creates an AWS S3 bucket directly (no ComponentResource wrapper).
    
    Creates:
        - aws.s3.Bucket (actual AWS resource visible in preview)
    
    Outputs:
        - bucket_name: S3 bucket name
        - bucket_arn: S3 bucket ARN
        - bucket_id: S3 bucket ID
    """
    
    def __init__(self, name: str, config: Dict[str, Any], **kwargs):
        """Initialize S3 bucket atomic template"""
        self.cfg = S3BucketAtomicConfig(**config)
        super().__init__(name, config, **kwargs)
        self.bucket: aws.s3.Bucket = None
    
    def get_metadata(self):
        """Get template metadata"""
        return {
            "name": "S3 Bucket",
            "description": "Creates an AWS S3 bucket",
            "version": "1.0.0"
        }
    
    def create_infrastructure(self) -> Dict[str, Any]:
        """Create S3 bucket directly - shows as actual AWS resource in preview"""
        self.bucket = aws.s3.Bucket(
            f"{self.name}-bucket",
            bucket=self.cfg.bucket_name,
            tags=self.cfg.tags or {"Name": self.cfg.bucket_name or f"{self.name}-bucket"},
            opts=self.resource_options
        )
        
        pulumi.export(f"{self.name}_bucket_name", self.bucket.bucket)
        pulumi.export(f"{self.name}_bucket_arn", self.bucket.arn)
        
        return self.get_outputs()
    
    def get_outputs(self) -> Dict[str, Any]:
        """Get S3 bucket outputs"""
        if not self.bucket:
            raise RuntimeError(f"S3 bucket {self.name} not created")
        
        return {
            "bucket_name": self.bucket.bucket,
            "bucket_arn": self.bucket.arn,
            "bucket_id": self.bucket.id,
        }
