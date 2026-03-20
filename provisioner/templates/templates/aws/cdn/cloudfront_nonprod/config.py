"""Configuration for CloudFront NonProd template"""
from typing import Optional, Dict, Any, List
from pathlib import Path

from provisioner.utils.config_loader import TemplateConfigLoader


class CloudFrontNonProdConfig:
    """
    Configuration for CloudFront NonProd template

    Loads defaults from defaults.yaml with runtime override support.
    """

    def __init__(self, raw_config: Dict[str, Any]):
        self.raw_config = raw_config
        self.parameters = self.raw_config.get('parameters', {}).get('aws', {}) or self.raw_config.get('parameters', {})

        # Load defaults from YAML file
        template_dir = Path(__file__).parent
        self.config_loader = TemplateConfigLoader(template_dir)
        self.defaults = self.config_loader.config

        # Core attributes
        self.environment = self.raw_config.get('environment', 'nonprod')
        self.region = self.raw_config.get('region', 'us-east-1')

        # Merge default tags with runtime tags
        default_tags = self.defaults.get('tags', {})
        runtime_tags = self.raw_config.get('tags', {})
        self.tags = {**default_tags, **runtime_tags}

    def get_parameter(self, key: str, default: Any = None) -> Any:
        """Get a parameter from the configuration."""
        return self.parameters.get(key, default)

    @property
    def project_name(self) -> str:
        """Get project name from config."""
        return (
            self.get_parameter('projectName') or
            self.get_parameter('project_name') or
            self.raw_config.get('projectName') or
            self.raw_config.get('project_name') or
            'default-cloudfront'
        )

    # CloudFront-specific property accessors
    @property
    def cloudfront_enabled(self) -> bool:
        """Get CloudFront enabled status from defaults.yaml."""
        return self.config_loader.get('cloudfront.enabled', True)

    @property
    def cloudfront_comment(self) -> str:
        """Get CloudFront comment from defaults.yaml."""
        return self.config_loader.get('cloudfront.comment', f'CloudFront distribution for {self.project_name}')

    @property
    def cloudfront_price_class(self) -> str:
        """Get CloudFront price class — checks flat config (governance) then defaults.yaml."""
        return self.get_parameter('cloudfront_price_class') or self.config_loader.get('cloudfront.price_class', 'PriceClass_100')

    @property
    def cloudfront_default_root_object(self) -> str:
        """Get CloudFront default root object from defaults.yaml."""
        return self.config_loader.get('cloudfront.default_root_object', 'index.html')

    # Storage objects property accessors
    @property
    def storage_files(self) -> List[Dict[str, Any]]:
        """Get storage files configuration from defaults.yaml."""
        return self.config_loader.get('storage_objects.files', [])

    def get_storage_file_config(self, file_name: str) -> Optional[Dict[str, Any]]:
        """Get configuration for a specific storage file.

        Args:
            file_name: Name of the file (e.g., 'index.html')

        Returns:
            File configuration dict or None if not found
        """
        files = self.storage_files
        for file_config in files:
            if file_config.get('name') == file_name:
                return file_config
        return None

    # Inherited configurations from static website template
    @property
    def bucket_versioning(self) -> bool:
        """Get S3 bucket versioning from defaults.yaml."""
        return self.config_loader.get('bucket.versioning', False)

    @property
    def bucket_force_destroy(self) -> bool:
        """Get S3 bucket force destroy setting from defaults.yaml."""
        return self.config_loader.get('bucket.force_destroy', True)

    @property
    def website_index_document(self) -> str:
        """Get website index document from defaults.yaml."""
        return self.config_loader.get('website.index_document', 'index.html')

    @property
    def website_error_document(self) -> str:
        """Get website error document from defaults.yaml."""
        return self.config_loader.get('website.error_document', 'error.html')

    @property
    def public_access_config(self) -> Dict[str, bool]:
        """Get public access configuration from defaults.yaml."""
        return self.config_loader.get('public_access', {})

    @staticmethod
    def get_config_schema() -> Dict[str, Any]:
        """Get JSON schema for UI configuration."""
        return {
            "type": "object",
            "properties": {
                "project_name": {
                    "type": "string",
                    "title": "Project Name",
                    "description": "Project Name",
                    "help_text": "Name of your project for resource tagging and tracking",
                    "placeholder": "my-project",
                    "group": "Essentials",
                    "isEssential": True,
                    "order": 0
                },
                "region": {
                    "type": "string",
                    "title": "AWS Region",
                    "description": "AWS Region",
                    "default": "us-east-1",
                    "enum": ["us-east-1", "us-east-2", "us-west-1", "us-west-2", "eu-west-1", "eu-central-1"],
                    "group": "Essentials",
                    "isEssential": True,
                    "order": 1
                },
                "cloudfront_enabled": {
                    "type": "boolean",
                    "title": "Distribution Enabled",
                    "description": "Whether the CloudFront distribution is enabled",
                    "default": True,
                    "group": "CDN Settings",
                    "isEssential": True,
                    "order": 10
                },
                "cloudfront_price_class": {
                    "type": "select",
                    "title": "Price Class",
                    "description": "CloudFront price class determining global edge locations",
                    "default": "PriceClass_100",
                    "options": [
                        {"label": "PriceClass_100 (US, Canada, Europe)", "value": "PriceClass_100"},
                        {"label": "PriceClass_200 (+ Asia, Africa)", "value": "PriceClass_200"},
                        {"label": "PriceClass_All (All Edge Locations)", "value": "PriceClass_All"}
                    ],
                    "group": "CDN Settings",
                    "isEssential": True,
                    "order": 11
                },
                "cloudfront_default_root_object": {
                    "type": "string",
                    "title": "Default Root Object",
                    "description": "Default file to serve for root requests",
                    "default": "index.html",
                    "group": "CDN Settings",
                    "isEssential": True,
                    "order": 12
                },
                "bucket_versioning": {
                    "type": "boolean",
                    "title": "Versioning Enabled",
                    "description": "Enable S3 bucket versioning",
                    "default": True,
                    "group": "Origin Bucket",
                    "isEssential": True,
                    "order": 20
                },
                "bucket_force_destroy": {
                    "type": "boolean",
                    "title": "Force Destroy",
                    "description": "Allow bucket deletion even if not empty",
                    "default": True,
                    "group": "Origin Bucket",
                    "isEssential": True,
                    "order": 21
                },
                "website_index_document": {
                    "type": "string",
                    "title": "Index Document",
                    "description": "Default file for directory requests",
                    "default": "index.html",
                    "group": "Origin Bucket",
                    "isEssential": True,
                    "order": 22
                },
                "website_error_document": {
                    "type": "string",
                    "title": "Error Document",
                    "description": "Error page for 404 responses",
                    "default": "error.html",
                    "group": "Origin Bucket",
                    "isEssential": True,
                    "order": 23
                },
            },
            "required": ["project_name", "region"]
        }
