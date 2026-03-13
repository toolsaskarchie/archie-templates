"""
Azure Static Website Template - Pattern B Implementation

Deploys an Archie-branded static website to Azure Storage.
Uses PulumiAtomicFactory for resource creation and standardized metadata.
"""

from typing import Any, Dict, List, Optional
import random
import string
import os
import tempfile
from pathlib import Path
import boto3
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
    """
    
    def __init__(self, name: str = None, config: Dict[str, Any] = None, **kwargs):
        """Initialize Azure static website template"""
        raw_config = config or kwargs or {}
        if name is None:
            name = raw_config.get('websiteName', 'azure-static-website')
        super().__init__(name, raw_config)
        self.cfg = AzureStaticWebsiteConfig(raw_config)
        self.resource_group = None
        self.storage_account = None
        self.temp_dir: Optional[tempfile.TemporaryDirectory] = None

        environment = os.getenv("ENVIRONMENT", "sandbox")
        self.SOURCE_BUCKET = f"archie-static-website-source-{environment}"
        self.SOURCE_FILES = ["index.html", "styles.css", "archie-logo.png"]

    def _download_source_files(self, site_name: str = None, stack_name: str = None) -> List[Dict[str, Any]]:
        """Download branded files from Archie S3 source bucket."""
        self.temp_dir = tempfile.TemporaryDirectory()
        temp_path = Path(self.temp_dir.name)
        try:
            s3 = boto3.client("s3", region_name="us-east-1")
            downloaded: List[Dict[str, Any]] = []
            for file_key in self.SOURCE_FILES:
                local_path = temp_path / file_key
                s3.download_file(self.SOURCE_BUCKET, file_key, str(local_path))
                if file_key == "index.html":
                    self._customize_html(local_path, site_name=site_name, stack_name=stack_name)
                if file_key.endswith(('.png', '.jpg', '.jpeg', '.gif')):
                    with open(local_path, 'rb') as f:
                        content = f.read()
                else:
                    with open(local_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                downloaded.append({"content": content, "key": file_key, "content_type": self._get_content_type(file_key)})
            return downloaded
        except Exception as e:
            print(f"[AZURE-STATIC-WEBSITE] Fallback to embedded content: {e}")
            return self._get_embedded_files(site_name, stack_name)

    def _get_embedded_files(self, site_name: str = None, stack_name: str = None) -> List[Dict[str, Any]]:
        import datetime
        ts = datetime.datetime.now().strftime("%B %d, %Y at %I:%M %p UTC")
        html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><title>Deployment Success</title>
<link rel="stylesheet" href="styles.css"></head><body>
<div style="font-family:sans-serif;text-align:center;padding:50px;">
<h1>🎉 Deployment Successful!</h1><p>Your Azure Static Website is live.</p>
<div style="background:#f4f4f4;padding:20px;border-radius:8px;display:inline-block;text-align:left;">
<p><strong>Site:</strong> {site_name}</p><p><strong>Stack:</strong> {stack_name}</p>
<p><strong>Time:</strong> {ts}</p></div></div></body></html>"""
        css = "body { background: #fafafa; color: #333; }"
        return [
            {"content": html, "key": "index.html", "content_type": "text/html"},
            {"content": css, "key": "styles.css", "content_type": "text/css"},
        ]

    def _get_content_type(self, file_key: str) -> str:
        ext_map = {".html": "text/html", ".css": "text/css", ".png": "image/png", ".jpg": "image/jpeg"}
        return ext_map.get(Path(file_key).suffix, "text/plain")

    def _customize_html(self, html_path: Path, site_name: str = None, stack_name: str = None) -> None:
        import datetime
        with open(html_path, 'r', encoding='utf-8') as f:
            content = f.read()
        for k, v in {
            '{{DEPLOYMENT_NAME}}': stack_name or self.name,
            '{{BUCKET_NAME}}': site_name or "unknown",
            '{{TIMESTAMP}}': datetime.datetime.now().strftime("%B %d, %Y at %I:%M %p UTC"),
            '{{LOGO_URL}}': "archie-logo.png",
        }.items():
            content = content.replace(k, str(v))
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(content)

    def create_infrastructure(self) -> Dict[str, Any]:
        """Deploy infrastructure using factory pattern"""
        random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
        
        # 1. Resource Group
        self.resource_group = factory.create(
            "azure-native:resources:ResourceGroup",
            f"{self.name}-rg",
            resource_group_name=self.cfg.resourceGroup or f"rg-{self.name}-{random_suffix}",
            location=self.cfg.location,
            tags={"ManagedBy": "Archie", "Template": "azure-static-website"}
        )
        
        # 2. Storage Account
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
            tags={"ManagedBy": "Archie"}
        )
        
        # 3. Static Website Enablement
        factory.create(
            "azure-native:storage:StorageAccountStaticWebsite",
            f"{self.name}-static",
            account_name=self.storage_account.name,
            resource_group_name=self.resource_group.name,
            index_document="index.html",
            error404_document="index.html"
        )
        
        # 4. Upload website files
        files = self._download_source_files(site_name=sa_name, stack_name=self.name)
        for f in files:
            file_key = f["key"]
            props = {
                "account_name": self.storage_account.name,
                "resource_group_name": self.resource_group.name,
                "container_name": "$web",
                "blob_name": file_key,
                "content_type": f["content_type"],
                "type": "Block",
            }
            if isinstance(f["content"], bytes):
                temp_file = Path(self.temp_dir.name) / file_key
                props["source"] = pulumi.FileAsset(str(temp_file))
            else:
                props["source"] = pulumi.StringAsset(f["content"])
            factory.create("azure-native:storage:Blob", f"{self.name}-{file_key.replace('.', '-')}", **props)

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
            "marketplace_group": "WEBSITES"
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
                    "title": "Resource Group"
                },
                "location": {
                    "type": "string",
                    "title": "Azure Region",
                    "default": "eastus"
                }
            },
            "required": []
        }
