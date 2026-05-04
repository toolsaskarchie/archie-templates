"""Configuration for AWS S3 Static Website template."""
from typing import Optional, Dict, Any


class StaticWebsiteConfig:
    """Configuration specific to the S3 Static Website template.
    
    Configuration for static website-specific parameters
    like bucket naming, CloudFront options, custom domains, etc.
    """
    
    def __init__(self, raw_config: Dict[str, Any]):
        self.raw_config = raw_config
        self.parameters = self.raw_config.get('parameters', {}).get('aws', {}) or self.raw_config.get('parameters', {})
        
        # Core attributes accessed directly in pulumi.py
        self.environment = self.raw_config.get('environment', 'nonprod')
        self.region = self.raw_config.get('region', 'us-east-1')
        self.tags = self.raw_config.get('tags', {})
    
    def get_parameter(self, key: str, default: Any = None) -> Any:
        """Get a parameter from the configuration."""
        return self.parameters.get(key, default)
    
    @property
    def project_name(self) -> str:
        """Get the project name."""
        return (
            self.get_parameter('projectName') or 
            self.get_parameter('project_name') or 
            self.raw_config.get('parameters', {}).get('project_name') or
            self.raw_config.get('project_name') or
            self.raw_config.get('projectName') or
            # Fallback with random suffix to avoid collisions (Trigger Deploy)
            f"website-{__import__('random').randint(1000, 9999)}"
        )
    
    @property
    def bucket_name_prefix(self) -> str:
        """Get custom bucket name prefix, defaults to 'static-site'."""
        return self.get_parameter('bucket_name_prefix', 'static-site')
    
    @property
    def enable_cloudfront(self) -> bool:
        """Whether to enable CloudFront CDN, defaults to False."""
        return self.get_parameter('enable_cloudfront', False)
    
    @property
    def custom_domain(self) -> Optional[str]:
        """Get custom domain if specified."""
        return self.get_parameter('custom_domain')
    
    @property
    def enable_https(self) -> bool:
        """Whether to enable HTTPS (requires CloudFront), defaults to False."""
        return self.get_parameter('enable_https', False)
    
    @property
    def index_document(self) -> str:
        """Get index document name, defaults to 'index.html'."""
        return self.get_parameter('index_document', 'index.html')
    
    @property
    def error_document(self) -> Optional[str]:
        """Get error document name if specified."""
        return self.get_parameter('error_document')
    
    @property
    def enable_versioning(self) -> bool:
        """Whether to enable S3 versioning, defaults to False."""
        return self.get_parameter('enable_versioning', False)
    
    @property
    def cors_allowed_origins(self) -> list:
        """Get CORS allowed origins list, empty if not specified."""
        return self.get_parameter('cors_allowed_origins', [])
    
    @property
    def lifecycle_rules(self) -> dict:
        """Get lifecycle rules configuration, empty if not specified."""
        return self.get_parameter('lifecycle_rules', {})
