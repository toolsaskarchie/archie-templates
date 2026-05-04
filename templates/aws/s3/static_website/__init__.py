"""S3 Static Website Template"""
from provisioner.templates.templates.aws.s3.static_website.pulumi import S3StaticWebsiteTemplate

# Alias for backward compatibility
FreeStaticWebsiteTemplate = S3StaticWebsiteTemplate

__all__ = ["S3StaticWebsiteTemplate", "FreeStaticWebsiteTemplate"]
