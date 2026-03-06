"""S3 Public Access Block Atomic Configuration"""
from typing import Any
from pydantic import Field, validator
from provisioner.templates.atomic.base import AtomicConfig


class S3PublicAccessBlockAtomicConfig(AtomicConfig):
    """S3 Public Access Block Atomic Configuration
    
    Attributes:
        bucket_id: S3 bucket ID or Pulumi Output
        block_public_acls: Block public ACLs
        block_public_policy: Block public bucket policies
        ignore_public_acls: Ignore public ACLs
        restrict_public_buckets: Restrict public bucket policies
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
    block_public_acls: bool = Field(
        default=False,
        description="Block public ACLs"
    )
    block_public_policy: bool = Field(
        default=False,
        description="Block public bucket policies"
    )
    ignore_public_acls: bool = Field(
        default=False,
        description="Ignore public ACLs"
    )
    restrict_public_buckets: bool = Field(
        default=False,
        description="Restrict public bucket policies"
    )
