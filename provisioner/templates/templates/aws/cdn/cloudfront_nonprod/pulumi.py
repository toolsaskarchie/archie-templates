"""
CloudFront NonProd Template

Deploys a well-architected CloudFront web distribution with S3 origin.
Creates S3 bucket for static website hosting, then adds CloudFront CDN for global delivery.

Architecture: Layer 3 template that CALLS aws-static-website template + uses CloudFront components
"""
from typing import Any, Dict, Optional
import pulumi
import pulumi_aws as aws

# Import Archie utils for consistent patterns
from provisioner.utils.aws import (
    ResourceNamer,
    get_standard_tags
)
from provisioner.templates.base import template_registry, InfrastructureTemplate
from provisioner.templates.templates.aws.cdn.cloudfront_nonprod.config import CloudFrontNonProdConfig
from provisioner.templates.templates.aws.s3.static_website.pulumi import S3StaticWebsiteTemplate
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory


@template_registry("aws-cloudfront-nonprod")
class CloudFrontNonProdTemplate(InfrastructureTemplate):
    """
    CloudFront NonProd Template - Pattern B Implementation
    
    Orchestrates:
    - S3 static website origin (via aws-static-website template)
    - CloudFront distribution for global delivery
    
    All resources created via factory pattern.
    """

    def __init__(self, name: str = None, config: Dict[str, Any] = None, **kwargs):
        """Initialize CloudFront template"""
        raw_config = config or kwargs or {}
        self.cfg = CloudFrontNonProdConfig(raw_config)

        if name is None:
            name = raw_config.get('projectName', 'cloudfront-nonprod')

        super().__init__(name, raw_config)

        self.s3_template: Optional[S3StaticWebsiteTemplate] = None
        self.distribution: Optional[aws.cloudfront.Distribution] = None

    def create_infrastructure(self) -> Dict[str, Any]:
        """Deploy infrastructure (implements abstract method)"""
        return self.create()

    def create(self) -> Dict[str, Any]:
        """Deploy CloudFront distribution with S3 origin using factory pattern"""
        
        # Initialize namer
        environment = self.cfg.environment or 'nonprod'
        namer = ResourceNamer(
            project=self.cfg.project_name,
            environment=environment,
            region=self.cfg.region,
            template="aws-cloudfront-nonprod"
        )
        
        # ========================================
        # STEP 1: CALL S3 STATIC WEBSITE TEMPLATE
        # ========================================
        s3_config = {
            "parameters": {
                "aws": {
                    "projectName": f"{self.cfg.project_name}-origin",
                    "environment": environment
                }
            }
        }

        self.s3_template = S3StaticWebsiteTemplate(
            name=f"{self.name}-s3-origin",
            config=s3_config
        )
        s3_outputs = self.s3_template.create_infrastructure()

        s3_bucket_name = s3_outputs.get('bucket_name')
        s3_website_url = s3_outputs.get('website_url')

        # ========================================
        # STEP 2: CREATE CLOUDFRONT DISTRIBUTION
        # ========================================
        tags = get_standard_tags(
            project=self.cfg.project_name,
            environment=environment,
            template="aws-cloudfront-nonprod"
        )
        tags.update(self.cfg.tags)

        # Prepare origins
        origins = [{
            "domain_name": pulumi.Output.from_input(s3_website_url).apply(
                lambda url: url.replace('http://', '').replace('https://', '').rstrip('/')
            ),
            "origin_id": f"S3-{self.cfg.project_name}",
            "custom_origin_config": {
                "http_port": 80,
                "https_port": 443,
                "origin_protocol_policy": "http-only",
                "origin_ssl_protocols": ["TLSv1.2"]
            }
        }]

        default_cache_behavior = {
            "target_origin_id": f"S3-{self.cfg.project_name}",
            "viewer_protocol_policy": "redirect-to-https",
            "allowed_methods": ["GET", "HEAD"],
            "cached_methods": ["GET", "HEAD"],
            "compress": True,
            "forwarded_values": {
                "query_string": False,
                "cookies": {"forward": "none"}
            },
            "min_ttl": 0,
            "default_ttl": 86400,
            "max_ttl": 31536000
        }

        self.distribution = factory.create(
            "aws:cloudfront:Distribution",
            f"{self.name}-distribution",
            origins=origins,
            default_cache_behavior=default_cache_behavior,
            enabled=self.cfg.cloudfront_enabled,
            comment=self.cfg.cloudfront_comment,
            price_class=self.cfg.cloudfront_price_class,
            default_root_object=self.cfg.cloudfront_default_root_object,
            custom_error_responses=[{
                "error_code": 404,
                "response_code": 404,
                "response_page_path": "/index.html",
                "error_caching_min_ttl": 300
            }],
            restrictions={
                "geo_restriction": {
                    "restriction_type": "none"
                }
            },
            viewer_certificate={
                "cloudfront_default_certificate": True
            },
            tags=tags
        )

        cloudfront_domain = self.distribution.domain_name
        cloudfront_url = pulumi.Output.concat("https://", cloudfront_domain)

        # Export outputs
        pulumi.export("distribution_id", self.distribution.id)
        pulumi.export("cloudfront_domain", cloudfront_domain)
        pulumi.export("cloudfront_url", cloudfront_url)
        pulumi.export("s3_bucket_name", s3_bucket_name)

        return {
            "distribution_id": self.distribution.id,
            "cloudfront_domain": cloudfront_domain,
            "cloudfront_url": cloudfront_url,
            "s3_bucket_name": s3_bucket_name,
            "s3_website_url": s3_website_url
        }

    def get_outputs(self) -> Dict[str, Any]:
        """Get template outputs"""
        if not self.distribution:
            return {}

        s3_outputs = self.s3_template.get_outputs() if self.s3_template else {}
        
        cloudfront_domain = self.distribution.domain_name
        cloudfront_url = pulumi.Output.concat("https://", cloudfront_domain)

        return {
            "distribution_id": self.distribution.id,
            "cloudfront_domain": cloudfront_domain,
            "cloudfront_url": cloudfront_url,
            "s3_bucket_name": s3_outputs.get("bucket_name"),
            "s3_website_url": s3_outputs.get("website_url")
        }

    @classmethod
    def get_metadata(cls):
        """Template metadata for marketplace registration"""
        from provisioner.templates.base.template import TemplateMetadata, TemplateCategory
        return TemplateMetadata(
            name="aws-cloudfront-nonprod",
            title="CloudFront CDN",
            description="Accelerates static content delivery globally. Chains a high-availability S3 origin with Amazon CloudFront for edge-caching excellence, automatic HTTPS, and low-latency access for users worldwide.",
            category=TemplateCategory.NETWORKING,
            version="1.0.0",
            author="InnovativeApps",
            tags=["cloudfront", "cdn", "s3", "global", "networking"],
            features=[
                "Global Content Delivery via CloudFront Edge",
                "Automated SSL/TLS (HTTPS) for security",
                "Edge Caching Policies for minimized origin load",
                "Orchestrated S3 Origin Deployment",
                "Built-in SPA routing support"
            ],
            estimated_cost="$0 - $2.00/month (traffic dependent)",
            complexity="intermediate",
            deployment_time="5-10 minutes",
            marketplace_group="WEBSITES"
        )

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        """Get configuration schema for the UI"""
        return CloudFrontNonProdConfig.get_config_schema()
