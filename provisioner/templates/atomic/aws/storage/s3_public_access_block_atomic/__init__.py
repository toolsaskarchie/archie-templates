"""S3 Public Access Block Atomic Template"""
from .pulumi import S3PublicAccessBlockAtomicTemplate
from .config import S3PublicAccessBlockAtomicConfig

__all__ = [
    "S3PublicAccessBlockAtomicTemplate",
    "S3PublicAccessBlockAtomicConfig",
]
