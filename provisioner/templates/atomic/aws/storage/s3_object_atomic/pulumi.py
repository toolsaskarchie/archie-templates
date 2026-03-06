"""S3 Object Template"""
from typing import Dict, Any
import pulumi
import pulumi_aws as aws

from provisioner.templates.atomic.base import AtomicTemplate
from .config import S3ObjectAtomicConfig


class S3ObjectAtomicTemplate(AtomicTemplate):
    """S3 Object Template
    
    Creates S3 object (uploads file or content) directly.
    
    Creates:
        - aws.s3.BucketObject (actual AWS resource, visible in preview)
    
    Outputs:
        - bucket_id: S3 bucket ID
        - key: S3 object key
        - etag: Object ETag
    """
    
    def __init__(self, name: str, config: Dict[str, Any], **kwargs):
        """Initialize S3 object atomic template"""
        self.cfg = S3ObjectAtomicConfig(**config)
        super().__init__(name, config, **kwargs)
        self.object: aws.s3.BucketObject = None
    
    def create_infrastructure(self) -> Dict[str, Any]:
        """Create S3 object directly - shows as actual AWS resource in preview"""
        object_args = {
            "bucket": self.cfg.bucket_id,
            "key": self.cfg.key,
            "opts": self.resource_options,
        }
        
        # Either source or content must be provided
        if self.cfg.source:
            object_args["source"] = self.cfg.source
        elif self.cfg.content:
            object_args["content"] = self.cfg.content
        else:
            raise ValueError("Either 'source' or 'content' must be provided")
        
        if self.cfg.content_type:
            object_args["content_type"] = self.cfg.content_type
        
        if self.cfg.acl:
            object_args["acl"] = self.cfg.acl
        
        self.object = aws.s3.BucketObject(
            f"{self.name}-object",
            **object_args
        )
        
        pulumi.export(f"{self.name}_key", self.object.key)
        pulumi.export(f"{self.name}_etag", self.object.etag)
        
        return self.get_outputs()

    def get_metadata(self):
        """Get template metadata"""
        return {
            "name": "S3 Object",
            "description": "Creates S3 object",
            "version": "1.0.0"
        }
    
    def get_outputs(self) -> Dict[str, Any]:
        """Get S3 object outputs"""
        if not self.object:
            raise RuntimeError(f"S3 object {self.name} not created")
        
        return {
            "bucket_id": self.object.bucket,
            "key": self.object.key,
            "etag": self.object.etag,
        }
