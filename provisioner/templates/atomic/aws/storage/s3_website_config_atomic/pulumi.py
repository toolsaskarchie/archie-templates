"""S3 Website Configuration Template"""
from typing import Dict, Any
import pulumi
import pulumi_aws as aws

from provisioner.templates.atomic.base import AtomicTemplate
from .config import S3WebsiteConfigAtomicConfig


class S3WebsiteConfigAtomicTemplate(AtomicTemplate):
    """S3 Website Configuration Template
    
    Creates S3 bucket website configuration directly.
    
    Creates:
        - aws.s3.BucketWebsiteConfigurationV2 (actual AWS resource, visible in preview)
    
    Outputs:
        - website_endpoint: S3 website endpoint
        - website_domain: S3 website domain
    """
    
    def __init__(self, name: str, config: Dict[str, Any], **kwargs):
        """Initialize S3 website configuration atomic template"""
        self.cfg = S3WebsiteConfigAtomicConfig(**config)
        super().__init__(name, config, **kwargs)
        self.website_config: aws.s3.BucketWebsiteConfigurationV2 = None
    
    def create_infrastructure(self) -> Dict[str, Any]:
        """Create S3 website configuration directly - shows as actual AWS resource in preview"""
        website_config_args = {
            "bucket": self.cfg.bucket_id,
            "index_document": aws.s3.BucketWebsiteConfigurationV2IndexDocumentArgs(
                suffix=self.cfg.index_document
            ),
            "opts": self.resource_options,
        }
        
        if self.cfg.error_document:
            website_config_args["error_document"] = aws.s3.BucketWebsiteConfigurationV2ErrorDocumentArgs(
                key=self.cfg.error_document
            )
        
        self.website_config = aws.s3.BucketWebsiteConfigurationV2(
            f"{self.name}-website-config",
            **website_config_args
        )
        
        pulumi.export(f"{self.name}_website_endpoint", self.website_config.website_endpoint)
        
        return self.get_outputs()

    def get_metadata(self):
        """Get template metadata"""
        return {
            "name": "S3 Website Config",
            "description": "Creates S3 website configuration",
            "version": "1.0.0"
        }
    
    def get_outputs(self) -> Dict[str, Any]:
        """Get S3 website configuration outputs"""
        if not self.website_config:
            raise RuntimeError(f"S3 website config {self.name} not created")
        
        return {
            "website_endpoint": self.website_config.website_endpoint,
            "website_domain": self.website_config.website_domain,
        }
