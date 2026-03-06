"""S3 Object Atomic Configuration"""
from typing import Optional, Any
from pydantic import Field, validator
from provisioner.templates.atomic.base import AtomicConfig


class S3ObjectAtomicConfig(AtomicConfig):
    """S3 Object Atomic Configuration
    
    Attributes:
        bucket_id: S3 bucket ID/name or Pulumi Output
        key: S3 object key (path)
        source: Local file path to upload
        content: Content string (alternative to source)
        content_type: Content type (MIME type)
        acl: ACL setting (e.g., "public-read")
    """
    
    bucket_id: Any = Field(
        ...,
        description="S3 bucket ID/name or Pulumi Output"
    )
    
    @validator('bucket_id', pre=True)
    @classmethod
    def validate_bucket_id(cls, v):
        # Accept Pulumi Output objects
        return v
    key: str = Field(
        ...,
        description="S3 object key (path)"
    )
    source: Optional[Any] = Field(
        default=None,
        description="Local file path or FileAsset to upload"
    )
    
    @validator('source', pre=True)
    @classmethod
    def validate_source(cls, v):
        # Accept FileAsset objects
        return v
    content: Optional[str] = Field(
        default=None,
        description="Content string (alternative to source)"
    )
    content_type: Optional[str] = Field(
        default=None,
        description="Content type (MIME type)"
    )
    acl: Optional[str] = Field(
        default=None,
        description="ACL setting (e.g., 'public-read')"
    )
