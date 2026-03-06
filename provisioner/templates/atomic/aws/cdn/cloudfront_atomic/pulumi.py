"""CloudFront Template - Creates CloudFront Distribution"""
from typing import Dict, Any
import pulumi
import pulumi_aws as aws

from provisioner.templates.atomic.base import AtomicTemplate
from .config import CloudFrontAtomicConfig


class CloudFrontAtomicTemplate(AtomicTemplate):
    """
    CloudFront Distribution Template
    
    Creates an AWS CloudFront distribution with configurable origins and cache behaviors.
    This is a foundational building block for CDN infrastructure.
    
    Creates:
        - aws.cloudfront.Distribution
    
    Outputs:
        - distribution_id: CloudFront distribution ID
        - domain_name: CloudFront domain name
        - arn: CloudFront distribution ARN
        - hosted_zone_id: Route 53 hosted zone ID for the distribution
    """
    
    def __init__(self, name: str, config: Dict[str, Any], **kwargs):
        """Initialize CloudFront atomic template
        
        Args:
            name: Resource name
            config: Configuration dictionary
            **kwargs: Additional arguments
        """
        self.cfg = CloudFrontAtomicConfig(**config)
        super().__init__(name, config, **kwargs)
        self.distribution: aws.cloudfront.Distribution = None
    
    def get_metadata(self):
        """Get template metadata"""
        return {
            "name": "CloudFront",
            "description": "Creates an AWS CloudFront distribution",
            "version": "1.0.0"
        }
    
    def create_infrastructure(self) -> Dict[str, Any]:
        """Create CloudFront distribution
        
        Returns:
            Dictionary with outputs
        """
        # Set defaults
        restrictions = self.cfg.restrictions or {
            "geo_restriction": {
                "restriction_type": "none"
            }
        }
        
        viewer_certificate = self.cfg.viewer_certificate or {
            "cloudfront_default_certificate": True
        }
        
        custom_error_responses = self.cfg.custom_error_responses or [{
            "error_code": 404,
            "response_code": 404,
            "response_page_path": f"/{self.cfg.default_root_object}",
            "error_caching_min_ttl": 300
        }]
        
        # Create CloudFront distribution using component
        self.distribution = aws.cloudfront.Distribution(
            self.name,
            origins=self.cfg.origins,
            default_cache_behavior=self.cfg.default_cache_behavior,
            enabled=self.cfg.enabled,
            comment=self.cfg.comment,
            price_class=self.cfg.price_class,
            default_root_object=self.cfg.default_root_object,
            custom_error_responses=custom_error_responses,
            restrictions=restrictions,
            viewer_certificate=viewer_certificate,
            aliases=self.cfg.aliases,
            tags=self.cfg.tags or {"Name": f"{self.name}-distribution"},
            opts=self.resource_options
        )
        
        # Export outputs
        pulumi.export(f"{self.name}_distribution_id", self.distribution.id)
        pulumi.export(f"{self.name}_domain_name", self.distribution.domain_name)
        pulumi.export(f"{self.name}_arn", self.distribution.arn)
        
        return self.get_outputs()
    
    def get_outputs(self) -> Dict[str, Any]:
        """Get CloudFront outputs
        
        Returns:
            Dictionary with resource outputs
        """
        if not self.distribution:
            raise RuntimeError(f"CloudFront distribution {self.name} not created")
        
        return {
            "distribution_id": self.distribution.id,
            "domain_name": self.distribution.domain_name,
            "arn": self.distribution.arn,
            "hosted_zone_id": self.distribution.hosted_zone_id,
        }
