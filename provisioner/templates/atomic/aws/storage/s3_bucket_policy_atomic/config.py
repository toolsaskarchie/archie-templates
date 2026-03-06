"""S3 Bucket Policy Atomic Configuration"""
from typing import Any
from pydantic import Field, validator
from provisioner.templates.atomic.base import AtomicConfig


class S3BucketPolicyAtomicConfig(AtomicConfig):
    """S3 Bucket Policy Atomic Configuration
    
    Attributes:
        bucket_id: S3 bucket ID/name or Pulumi Output
        policy: JSON policy document as string or Pulumi Output
    """
    
    bucket_id: Any = Field(
        ...,
        description="S3 bucket ID/name or Pulumi Output"
    )
    policy: Any = Field(
        ...,
        description="JSON policy document as string or Pulumi Output"
    )
    
    @validator('bucket_id', 'policy', pre=True)
    @classmethod
    def validate_outputs(cls, v):
        # Accept Pulumi Output objects
        return v
