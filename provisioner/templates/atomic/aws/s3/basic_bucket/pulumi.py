"""
S3 Bucket Demo Template
Simple S3 bucket with versioning and lifecycle policies.
Uses Archie's standardized utilities and S3 components for consistent configuration.
"""
from typing import Any, Dict, Optional
import pulumi
import pulumi_aws as aws
from provisioner.templates.base import (
    InfrastructureTemplate,
    template_registry
)
from provisioner.utils.aws import get_standard_tags
from provisioner.templates.atomic.aws.s3.basic_bucket.config import BasicBucketConfig


@template_registry("aws-basic-bucket")
class S3BucketTemplate(InfrastructureTemplate):
    """
    Simple S3 Bucket Template - Component-based Implementation
    Creates S3 bucket directly (no ComponentResource wrapper).
    Perfect for testing deployment flow without complex infrastructure.
    """
    
    def __init__(self, name: str = None, config: Dict[str, Any] = None, **kwargs):
        raw_config = config or kwargs or {}
        if name is None:
            name = raw_config.get('bucketName', 's3-demo-bucket')
        super().__init__(name, raw_config)
        self.cfg = BasicBucketConfig(raw_config)
        self.bucket = None
    
    def create_infrastructure(self) -> Dict[str, Any]:
        """Create S3 bucket infrastructure"""
        # Generate bucket name
        bucket_name = self.cfg.bucketName or f"{self.name}-{pulumi.get_stack()}"
        
        # Standard tags
        tags = get_standard_tags(
            project=self.cfg.projectName or "demo",
            environment="nonprod",
            template="s3-demo-bucket"
        )
        
        # Create S3 bucket using component
        # Use pattern: aws.s3.Bucket(f"{self.name}-bucket", ...)
        self.bucket = aws.s3.Bucket(
            f"{self.name}-bucket",
            bucket=bucket_name,
            tags=tags,
            versioning={"enabled": self.cfg.enableVersioning},
            server_side_encryption_configuration={
                "rule": {
                    "apply_server_side_encryption_by_default": {
                        "sse_algorithm": "AES256"
                    }
                }
            }
        )
        
        # Lifecycle rule (optional) - direct AWS resource
        if self.cfg.lifecycleDays > 0:
            aws.s3.BucketLifecycleConfigurationV2(
                f"{self.name}-lifecycle",
                bucket=self.bucket.id,
                rules=[{
                    "id": "expire-old-objects",
                    "status": "Enabled",
                    "expiration": {
                        "days": self.cfg.lifecycleDays
                    }
                }]
            )
        
        # Export outputs
        pulumi.export("bucket_name", self.bucket.bucket)
        pulumi.export("bucket_arn", self.bucket.arn)
        pulumi.export("bucket_region", self.cfg.region)
        
        return {
            "template_name": "s3-demo-bucket",
            "outputs": {
                "bucket_name": bucket_name,
                "bucket_arn": "Output after deployment",
                "bucket_region": self.cfg.region
            }
        }
    
    @classmethod
    def get_metadata(cls) -> Dict[str, Any]:
        """Get template metadata"""
        return {
            "name": "s3-demo-bucket",
            "title": "S3 Basic Bucket",
            "subtitle": "Simple S3 bucket for testing",
            "description": "Creates a basic S3 bucket with versioning and encryption",
            "category": "storage",
            "provider": "aws",
            "icon": "🗄️",
            "version": "1.0.0",
            "status": "stable"
        }
    
    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        """Get configuration schema"""
        return {
            "type": "object",
            "properties": {
                "bucketName": {
                    "type": "string",
                    "title": "Bucket Name",
                    "description": "Name for the S3 bucket"
                },
                "projectName": {
                    "type": "string",
                    "title": "Project Name",
                    "default": "demo"
                },
                "region": {
                    "type": "string",
                    "title": "AWS Region",
                    "default": "us-east-1"
                },
                "enableVersioning": {
                    "type": "boolean",
                    "title": "Enable Versioning",
                    "default": True
                },
                "lifecycleDays": {
                    "type": "integer",
                    "title": "Lifecycle Days",
                    "default": 90
                }
            },
            "required": ["bucketName"]
        }
