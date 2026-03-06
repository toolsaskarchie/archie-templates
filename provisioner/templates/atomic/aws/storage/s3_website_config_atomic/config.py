"""S3 Website Configuration Atomic Configuration"""
from typing import Optional, Dict, Any
from pydantic import Field, validator
from provisioner.templates.atomic.base import AtomicConfig


class S3WebsiteConfigAtomicConfig(AtomicConfig):
    """S3 Website Configuration Atomic Configuration
    
    Attributes:
        bucket_id: S3 bucket ID or Pulumi Output
        index_document: Index document (default: index.html)
        error_document: Error document (optional)
    """
    
    bucket_id: Any = Field(
        ...,
        description="S3 bucket ID or Pulumi Output"
    )
    
    @validator('bucket_id', pre=True)
    @classmethod
    def validate_bucket_id(cls, v):
        # Accept Pulumi Output objects
        return v
    index_document: str = Field(
        default="index.html",
        description="Index document"
    )
    error_document: Optional[str] = Field(
        default=None,
        description="Error document"
    )
