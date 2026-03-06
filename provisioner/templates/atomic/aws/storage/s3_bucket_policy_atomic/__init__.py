"""S3 Bucket Policy Atomic Template"""
from .pulumi import S3BucketPolicyAtomicTemplate
from .config import S3BucketPolicyAtomicConfig

__all__ = [
    "S3BucketPolicyAtomicTemplate",
    "S3BucketPolicyAtomicConfig",
]
