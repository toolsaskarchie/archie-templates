"""Configuration for CloudFront NonProd template"""
from typing import Optional, Dict, Any, List
from pathlib import Path

from provisioner.utils.config_loader import TemplateConfigLoader

# Import shared schema functions for consistent UI
from provisioner.templates.shared.aws_schema import (
    get_project_env_schema,
    get_observability_schema,
    get_cdn_storage_schema
)


class CloudFrontNonProdConfig:
    """
    Configuration for CloudFront NonProd template

    Loads defaults from defaults.yaml with runtime override support.
    """

    def __init__(self, raw_config: Dict[str, Any]):
        self.raw_config = raw_config
        self.parameters = self.raw_config.get('parameters', {}).get('aws', {})

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
        """Get CloudFront price class from defaults.yaml."""
        return self.config_loader.get('cloudfront.price_class', 'PriceClass_100')

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
        from provisioner.templates.shared.aws_schema import (
            get_project_env_schema,
            get_cdn_storage_schema,
            get_observability_schema
        )
        return {
            "type": "object",
            "properties": {
                **get_project_env_schema(order_offset=0),
                **get_cdn_storage_schema(order_offset=10),
                **get_observability_schema(order_offset=200),
            },
            "required": ["project_name", "region"]
        }
