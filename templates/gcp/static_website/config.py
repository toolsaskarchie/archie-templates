"""Configuration for GCP Static Website template."""
from typing import Optional, Dict, Any


class GCPStaticWebsiteConfig:
    """Configuration specific to the GCP Static Website template.
    
    Configuration for static website-specific parameters
    like bucket naming, Cloud CDN options, custom domains, etc.
    """
    
    def __init__(self, raw_config: Dict[str, Any]):
        self.raw_config = raw_config
        self.parameters = self.raw_config.get('parameters', {}).get('gcp', {})
        
        # Core attributes accessed directly in pulumi.py
        self.environment = self.raw_config.get('environment', 'nonprod')
        self.region = self.raw_config.get('region', 'us-central1')
        
        # Project ID: check config, parameters, credentials SA, then fallback
        self.project = (
            self.raw_config.get('project') or
            self.raw_config.get('project_id') or
            self.parameters.get('project', '') or
            self.parameters.get('project_id', '') or
            self.raw_config.get('credentials', {}).get('gcp', {}).get('project_id', '') or
            ''
        )
        
        # Labels (GCP equivalent of tags)
        self.tags = self.raw_config.get('tags', {})
        self.labels = self.raw_config.get('labels', {})
        
        # Validate required fields
        self._validate()
    
    def _validate(self):
        """Validate configuration"""
        # Static website template uses default project if not provided
        if not self.project:
            print("[CONFIG WARNING] No GCP project ID provided — deploy will use SA default")
    
    def get_parameter(self, key: str, default: Any = None) -> Any:
        """Get a parameter from the configuration."""
        return self.parameters.get(key, default)
    
    @property
    def bucket_name_prefix(self) -> str:
        """Get custom bucket name prefix, defaults to 'archie-gcp'."""
        return self.get_parameter('bucket_name_prefix', 'archie-gcp')
    
    @property
    def enable_cdn(self) -> bool:
        """Whether to enable Cloud CDN, defaults to False."""
        return self.get_parameter('enable_cdn', False)
    
    @property
    def custom_domain(self) -> Optional[str]:
        """Get custom domain if specified."""
        return self.get_parameter('custom_domain')
    
    @property
    def enable_https(self) -> bool:
        """Whether to enable HTTPS (requires Load Balancer), defaults to False."""
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
        """Whether to enable bucket versioning, defaults to False."""
        return self.get_parameter('enable_versioning', False)
    
    @property
    def cors_allowed_origins(self) -> list:
        """Get CORS allowed origins list, empty if not specified."""
        return self.get_parameter('cors_allowed_origins', [])
    
    @property
    def lifecycle_rules(self) -> dict:
        """Get lifecycle rules configuration, empty if not specified."""
        return self.get_parameter('lifecycle_rules', {})
    
    @property
    def location(self) -> str:
        """Get bucket location (alias for region)."""
        return self.get_parameter('location', self.region)