"""S3 Bucket Atomic Template"""
from .pulumi import S3BucketAtomicTemplate
from .config import S3BucketAtomicConfig

__all__ = [
    "S3BucketAtomicTemplate",
    "S3BucketAtomicConfig",
]
