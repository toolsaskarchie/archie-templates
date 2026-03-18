"""
Azure Static Website Template - Pattern B Implementation

Deploys an Archie-branded static website to Azure Storage.
Uses PulumiAtomicFactory for resource creation and standardized metadata.
"""

from typing import Any, Dict, List, Optional
import random
import string
import tempfile
import os
from pathlib import Path
import pulumi
from provisioner.templates.base import template_registry, InfrastructureTemplate
from .config import AzureStaticWebsiteConfig
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory


@template_registry("azure-static-website")
class AzureStaticWebsiteTemplate(InfrastructureTemplate):
    """
    Azure Static Website Template

    Creates:
    - Azure Resource Group
    - Azure Storage Account with static website hosting
    - Blob uploads to $web container (index.html, styles.css)
    """

    def __init__(self, name: str = None, config: Dict[str, Any] = None, **kwargs):
        """Initialize Azure static website template"""
        raw_config = config or kwargs or {}
        if name is None:
            name = raw_config.get('websiteName', raw_config.get('projectName', 'azure-static-website'))
        super().__init__(name, raw_config)
        self.cfg = AzureStaticWebsiteConfig(raw_config)
        self.resource_group = None
        self.storage_account = None
        self.temp_dir: Optional[tempfile.TemporaryDirectory] = None

        # Environment settings for source files (stored in AWS S3)
        environment = os.getenv("ENVIRONMENT", "sandbox")
        self.SOURCE_BUCKET = f"archie-static-website-source-{environment}"
        self.SOURCE_REGION = "us-east-1"
        self.SOURCE_FILES = ["index-azure.html", "styles.css"]

    def _download_source_files(self, stack_name: str = None) -> List[Dict[str, str]]:
        """Download HTML/CSS files from Archie's source bucket and customize with deployment info"""
        self.temp_dir = tempfile.TemporaryDirectory()
        temp_path = Path(self.temp_dir.name)

        try:
            import boto3
            s3_client = boto3.client("s3", region_name=self.SOURCE_REGION)
        except Exception as e:
            print(f"[TEMPLATE ERROR] Failed to create S3 client for source files: {e}")
            return self._get_embedded_files(stack_name)

        downloaded_files = []
        for file_key in self.SOURCE_FILES:
            try:
                local_path = temp_path / file_key
                s3_client.download_file(self.SOURCE_BUCKET, file_key, str(local_path))

                # Rename cloud-specific index back to index.html for deployment
                deploy_key = "index.html" if file_key.startswith("index-") else file_key

                if file_key.startswith("index-"):
                    self._customize_html(local_path, stack_name=stack_name)

                with open(local_path, 'r', encoding='utf-8') as f:
                    file_content = f.read()

                content_type_map = {
                    ".html": "text/html", ".css": "text/css",
                    ".png": "image/png", ".svg": "image/svg+xml",
                }
                ext = os.path.splitext(deploy_key)[1]
                content_type = content_type_map.get(ext, "text/plain")

                downloaded_files.append({"content": file_content, "key": deploy_key, "content_type": content_type})
            except Exception as e:
                print(f"[TEMPLATE ERROR] Failed to download {file_key}: {e}")
                if file_key.startswith("index-"):
                    return self._get_embedded_files(stack_name)

        return downloaded_files

    def _get_embedded_files(self, stack_name: str = None) -> List[Dict[str, Any]]:
        """Default content if source bucket is unavailable"""
        import datetime
        timestamp = datetime.datetime.now().strftime("%B %d, %Y at %I:%M %p UTC")

        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Deployment Success</title>
</head>
<body style="font-family: sans-serif; text-align: center; padding: 50px; background: #0f1117; color: #e0e0e0;">
    <h1>Deployment Successful!</h1>
    <p>Your Azure Static Website is live.</p>
    <div style="background: #1a1d27; padding: 20px; border-radius: 8px; display: inline-block; text-align: left;">
        <p><strong>Stack:</strong> {stack_name or self.name}</p>
        <p><strong>Region:</strong> {self.cfg.location}</p>
        <p><strong>Time:</strong> {timestamp}</p>
    </div>
</body>
</html>"""

        return [
            {"content": html_content, "key": "index.html", "content_type": "text/html"},
        ]

    def _customize_html(self, html_path: Path, stack_name: str = None) -> None:
        """Inject deployment-specific information into the HTML"""
        import datetime

        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        project_name = (
            self.config.get('parameters', {}).get('azure', {}).get('projectName') or
            self.config.get('projectName') or
            self.config.get('project_name') or
            self.name or 'your-project'
        )
        environment = self.config.get('environment', 'nonprod')
        region = self.cfg.location
        timestamp = datetime.datetime.now().strftime("%B %d, %Y at %I:%M %p UTC")

        if not stack_name:
            stack_name = self.config.get('name', self.name)

        logo_url = f"https://{self.SOURCE_BUCKET}.s3.{self.SOURCE_REGION}.amazonaws.com/archie-logo.png"

        replacements = {
            '{{DEPLOYMENT_NAME}}': stack_name, '{{PROJECT_NAME}}': project_name,
            '{{ENVIRONMENT}}': environment, '{{REGION}}': region,
            '{{TIMESTAMP}}': timestamp, '{{STACK_NAME}}': stack_name,
            '{{BUCKET_NAME}}': stack_name, '{{LOGO_URL}}': logo_url,
        }

        for placeholder, value in replacements.items():
            html_content = html_content.replace(placeholder, value)

        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

    def create_infrastructure(self) -> Dict[str, Any]:
        """Deploy infrastructure using factory pattern"""
        random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))

        # 1. Resource Group — use user-provided name or generate unique one
        rg_name = self.cfg.resourceGroup or f"rg-{self.name}-{random_suffix}"[:63]
        self.resource_group = factory.create(
            "azure-native:resources:ResourceGroup",
            f"{self.name}-rg",
            resource_group_name=rg_name,
            location=self.cfg.location,
            tags={"ManagedBy": "Archie", "Template": "azure-static-website"}
        )

        # 2. Storage Account (Azure can be very slow — 10 min timeout)
        sa_name = f"st{self.name.replace('-', '')[:14]}{random_suffix}"[:24].lower()
        self.storage_account = factory.create(
            "azure-native:storage:StorageAccount",
            f"{self.name}-storage",
            account_name=sa_name,
            resource_group_name=self.resource_group.name,
            location=self.cfg.location,
            sku={"name": "Standard_LRS"},
            kind="StorageV2",
            enable_https_traffic_only=True,
            tags={"ManagedBy": "Archie"},
            opts=pulumi.ResourceOptions(
                custom_timeouts=pulumi.CustomTimeouts(create="10m", update="10m", delete="5m")
            )
        )

        # 3. Static Website Enablement
        static_website = factory.create(
            "azure-native:storage:StorageAccountStaticWebsite",
            f"{self.name}-static",
            account_name=self.storage_account.name,
            resource_group_name=self.resource_group.name,
            index_document="index.html",
            error404_document="index.html"
        )

        # 4. Download source files and upload to $web container
        files = self._download_source_files(stack_name=self.name)
        for file_info in files:
            file_key = file_info["key"]
            file_content = file_info["content"]
            content_type = file_info["content_type"]

            factory.create(
                "azure-native:storage:Blob",
                f"{self.name}-{file_key.replace('.', '-')}",
                account_name=self.storage_account.name,
                resource_group_name=self.resource_group.name,
                container_name="$web",
                blob_name=file_key,
                source=pulumi.StringAsset(file_content),
                content_type=content_type,
                type="Block",
                opts=pulumi.ResourceOptions(depends_on=[static_website])
            )

        # 5. Construct URL
        website_url = self.storage_account.primary_endpoints.apply(
            lambda e: e.web if e and hasattr(e, 'web') else "pending"
        )

        pulumi.export("website_name", self.name)
        pulumi.export("resource_group", self.resource_group.name)
        pulumi.export("storage_account_name", self.storage_account.name)
        pulumi.export("website_url", website_url)

        return {
            "template_name": "azure-static-website",
            "outputs": {
                "website_name": self.name,
                "resource_group": self.resource_group.name,
                "storage_account_name": self.storage_account.name,
                "website_url": website_url
            }
        }

    def get_outputs(self) -> Dict[str, Any]:
        """Get template outputs"""
        if not self.storage_account: return {}
        website_url = self.storage_account.primary_endpoints.apply(
            lambda e: e.web if e and hasattr(e, 'web') else None
        )
        return {
            "website_name": self.name,
            "resource_group": self.resource_group.name if self.resource_group else None,
            "storage_account_name": self.storage_account.name,
            "website_url": website_url
        }

    def cleanup(self) -> None:
        """Clean up temporary files"""
        if self.temp_dir:
            self.temp_dir.cleanup()

    @classmethod
    def get_metadata(cls) -> Dict[str, Any]:
        """Template metadata (Pattern B)"""
        return {
            "name": "azure-static-website",
            "title": "Demo Static Website",
            "description": "Deploy an Archie-branded congratulations page on Azure Storage - perfect for your first Azure deployment!",
            "category": "website",
            "cloud": "azure",
            "version": "1.1.0",
            "author": "InnovativeApps",
            "tags": ["azure", "storage", "website", "static", "free"],
            "base_cost": "$0.00/month",
            "complexity": "low",
            "deployment_time": "3-5 minutes",
            "marketplace_group": "WEBSITES",
            "pillars": [
                {
                    "title": "Operational Excellence",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Managed static hosting with automated content deployment.",
                    "practices": [
                        "Infrastructure as Code with Pulumi for repeatable deployments",
                        "Automated content upload from versioned source bucket",
                        "Resource Group tagging for organization and tracking",
                        "Storage Account static website feature for zero-server hosting"
                    ]
                },
                {
                    "title": "Security",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "HTTPS-only access with Azure Storage security defaults.",
                    "practices": [
                        "HTTPS traffic only enforced on Storage Account",
                        "Azure Storage encryption at rest by default",
                        "No server-side code execution surface to attack",
                        "Resource Group isolation for access control"
                    ]
                },
                {
                    "title": "Reliability",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Azure Storage provides highly durable and available hosting.",
                    "practices": [
                        "Azure Storage 99.9% availability SLA for LRS",
                        "Triple replication within the storage stamp",
                        "Automatic failover within storage infrastructure",
                        "Embedded fallback content if source bucket is unavailable"
                    ]
                },
                {
                    "title": "Performance Efficiency",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Serverless static hosting with Azure global infrastructure.",
                    "practices": [
                        "Direct blob serving with no compute overhead",
                        "Azure global network for low-latency content delivery",
                        "Lightweight HTML/CSS assets for fast page loads",
                        "No cold start or server provisioning delays"
                    ]
                },
                {
                    "title": "Cost Optimization",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Near-zero cost for static website hosting on Azure Storage.",
                    "practices": [
                        "No compute instances or server costs",
                        "Standard_LRS tier for lowest storage pricing",
                        "Pay only for storage and egress bandwidth",
                        "No idle resources consuming budget"
                    ]
                },
                {
                    "title": "Sustainability",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Serverless architecture with minimal resource consumption.",
                    "practices": [
                        "No always-on compute instances",
                        "Azure commitment to 100% renewable energy by 2025",
                        "Efficient object storage with no over-provisioning",
                        "Minimal resource footprint for static content delivery"
                    ]
                }
            ]
        }

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        """Get configuration schema"""
        return {
            "type": "object",
            "properties": {
                "websiteName": {
                    "type": "string",
                    "title": "Website Name",
                    "default": "my-azure-site"
                },
                "resourceGroup": {
                    "type": "string",
                    "title": "Resource Group",
                    "description": "Optional — auto-generated if not provided"
                },
                "location": {
                    "type": "string",
                    "title": "Azure Region",
                    "default": "eastus"
                }
            },
            "required": ["websiteName"]
        }
