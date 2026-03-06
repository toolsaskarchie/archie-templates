"""S3 Public Access Block Template"""
from typing import Dict, Any
import pulumi
import pulumi_aws as aws

from provisioner.templates.atomic.base import AtomicTemplate
from .config import S3PublicAccessBlockAtomicConfig


class S3PublicAccessBlockAtomicTemplate(AtomicTemplate):
    """S3 Public Access Block Template
    
    Creates S3 bucket public access block settings directly.
    
    Creates:
        - aws.s3.BucketPublicAccessBlock (actual AWS resource, visible in preview)
    
    Outputs:
        - bucket_id: S3 bucket ID
    """
    
    def __init__(self, name: str, config: Dict[str, Any], **kwargs):
        """Initialize S3 public access block atomic template"""
        self.cfg = S3PublicAccessBlockAtomicConfig(**config)
        super().__init__(name, config, **kwargs)
        self.public_access_block: aws.s3.BucketPublicAccessBlock = None
    
    def create_infrastructure(self) -> Dict[str, Any]:
        """Create S3 public access block directly - shows as actual AWS resource in preview"""
        self.public_access_block = aws.s3.BucketPublicAccessBlock(
            f"{self.name}-public-access-block",
            bucket=self.cfg.bucket_id,
            block_public_acls=self.cfg.block_public_acls,
            block_public_policy=self.cfg.block_public_policy,
            ignore_public_acls=self.cfg.ignore_public_acls,
            restrict_public_buckets=self.cfg.restrict_public_buckets,
            opts=self.resource_options
        )
        
        pulumi.export(f"{self.name}_bucket_id", self.public_access_block.bucket)
        
        return self.get_outputs()

    def get_metadata(self):
        """Get template metadata"""
        return {
            "name": "S3 Public Access Block",
            "description": "Creates S3 public access block",
            "version": "1.0.0"
        }
    
    def get_outputs(self) -> Dict[str, Any]:
        """Get S3 public access block outputs"""
        if not self.public_access_block:
            raise RuntimeError(f"S3 public access block {self.name} not created")
        
        return {
            "bucket_id": self.public_access_block.bucket,
        }
