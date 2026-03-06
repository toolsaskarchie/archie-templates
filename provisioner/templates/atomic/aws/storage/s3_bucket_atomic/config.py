"""S3 Bucket Atomic Configuration"""
from typing import Optional, Dict
from pydantic import Field
from provisioner.templates.atomic.base import AtomicConfig


class S3BucketAtomicConfig(AtomicConfig):
    """S3 Bucket Atomic Configuration
    
    Attributes:
        bucket_name: Name of the S3 bucket (optional, auto-generated if not provided)
        tags: Resource tags
    """
    
    bucket_name: Optional[str] = Field(
        default=None,
        description="S3 bucket name (optional, auto-generated if not provided)"
    )
    tags: Dict[str, str] = Field(
        default_factory=dict,
        description="Resource tags"
    )
