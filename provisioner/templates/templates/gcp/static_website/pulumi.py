"""
GCP Static Website Template - Pattern B Implementation

Deploys an Archie-branded static website to Google Cloud Storage.
Uses PulumiAtomicFactory for resource creation and standardized metadata.
"""

from typing import Any, Dict, List, Optional
import tempfile
import os
from pathlib import Path
import boto3
import pulumi
import pulumi_gcp as gcp

from provisioner.templates.base import template_registry, InfrastructureTemplate
from .config import GCPStaticWebsiteConfig
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory


@template_registry("gcp-static-website")
class GCPStaticWebsiteTemplate(InfrastructureTemplate):
    """
    GCP Static Website Template
    
    Creates:
    - Cloud Storage bucket with static website hosting
    - Public access configuration via IAM
    - Archie-branded congratulations page (HTML/CSS/logo)
    """
    
    def __init__(self, name: str = None, config: Dict[str, Any] = None, **kwargs):
        """Initialize GCP static website template"""
        raw_config = config or kwargs or {}
        self.cfg = GCPStaticWebsiteConfig(raw_config)

        if name is None:
            name = raw_config.get('projectName', raw_config.get('websiteName', 'gcp-static-website'))

        super().__init__(name, raw_config)
        self.temp_dir: Optional[tempfile.TemporaryDirectory] = None
        self.bucket = None
        
        environment = os.getenv("ENVIRONMENT", "sandbox")
        self.SOURCE_BUCKET = f"archie-static-website-source-{environment}"
        self.SOURCE_PROJECT = self.cfg.project
        self.SOURCE_FILES = ["index-gcp.html", "styles.css"]

    def _download_source_files(self, bucket_name: str = None, stack_name: str = None) -> List[Dict[str, Any]]:
        """Download branded files from Archie S3 source bucket (worker runs in AWS Lambda)."""
        if not self.temp_dir:
            self.temp_dir = tempfile.TemporaryDirectory()
        temp_path = Path(self.temp_dir.name)

        try:
            s3 = boto3.client("s3", region_name="us-east-1")
            downloaded: List[Dict[str, Any]] = []
            for file_key in self.SOURCE_FILES:
                local_path = temp_path / file_key
                s3.download_file(self.SOURCE_BUCKET, file_key, str(local_path))

                # Rename cloud-specific index back to index.html for deployment
                deploy_key = "index.html" if file_key.startswith("index-") else file_key

                if file_key.startswith("index-"):
                    self._customize_html(local_path, bucket_name=bucket_name, stack_name=stack_name)

                if file_key.endswith(('.png', '.jpg', '.jpeg', '.gif')):
                    with open(local_path, 'rb') as f:
                        file_content = f.read()
                else:
                    with open(local_path, 'r', encoding='utf-8') as f:
                        file_content = f.read()

                downloaded.append({
                    "content": file_content,
                    "key": deploy_key,
                    "content_type": self._get_content_type(deploy_key)
                })
            return downloaded
        except Exception as e:
            print(f"[GCP-STATIC-WEBSITE] Fallback to embedded content: {e}")
            return self._get_embedded_files(bucket_name, stack_name)

    def _get_embedded_files(self, bucket_name: str = None, stack_name: str = None) -> List[Dict[str, Any]]:
        """Default content if source bucket is unavailable"""
        import datetime
        timestamp = datetime.datetime.now().strftime("%B %d, %Y at %I:%M %p UTC")
        
        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Deployment Success</title>
    <link rel="stylesheet" href="styles.css">
</head>
<body>
    <div style="font-family: sans-serif; text-align: center; padding: 50px;">
        <h1>🎉 Deployment Successful!</h1>
        <p>Your GCP Static Website is live.</p>
        <div style="background: #f4f4f4; padding: 20px; border-radius: 8px; display: inline-block; text-align: left;">
            <p><strong>Bucket:</strong> {bucket_name}</p>
            <p><strong>Stack:</strong> {stack_name}</p>
            <p><strong>Time:</strong> {timestamp}</p>
        </div>
    </div>
</body>
</html>"""

        css_content = "body { background: #fafafa; color: #333; }"
        
        return [
            {"content": html_content, "key": "index.html", "content_type": "text/html"},
            {"content": css_content, "key": "styles.css", "content_type": "text/css"}
        ]

    def _get_content_type(self, file_key: str) -> str:
        """Simple content type resolver"""
        ext_map = {".html": "text/html", ".css": "text/css", ".png": "image/png", ".jpg": "image/jpeg"}
        return ext_map.get(Path(file_key).suffix, "text/plain")

    def _customize_html(self, html_path: Path, bucket_name: str = None, stack_name: str = None) -> None:
        """Inject variables into HTML"""
        import datetime
        with open(html_path, 'r', encoding='utf-8') as f:
            content = f.read()

        project_name = (
            self.config.get('parameters', {}).get('gcp', {}).get('projectName') or
            self.config.get('projectName') or
            self.name or 'your-project'
        )
        environment = self.cfg.environment or 'nonprod'
        region = self.cfg.location

        replacements = {
            '{{DEPLOYMENT_NAME}}': stack_name or self.name,
            '{{PROJECT_NAME}}': project_name,
            '{{ENVIRONMENT}}': environment,
            '{{REGION}}': region,
            '{{STACK_NAME}}': stack_name or self.name,
            '{{BUCKET_NAME}}': bucket_name or "unknown",
            '{{TIMESTAMP}}': datetime.datetime.now().strftime("%B %d, %Y at %I:%M %p UTC"),
        }

        for k, v in replacements.items():
            content = content.replace(k, str(v))

        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(content)

    def create_infrastructure(self) -> Dict[str, Any]:
        """Deploy infrastructure using factory pattern"""
        import random
        import string
        
        # 1. Prepare bucket name
        random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
        safe_name = self.name.lower().replace('_', '-').replace(' ', '-')
        # GCS bucket names max 63 chars. Pulumi adds ~8 char suffix, so cap at 54.
        bucket_name = f"gcp-{safe_name}"[:47] + f"-{random_suffix}"
        bucket_name = bucket_name.strip('-')
        
        # 2. Create Bucket — use bucket_name as Pulumi logical name (also becomes GCP name)
        self.bucket = factory.create(
            "gcp:storage:Bucket",
            bucket_name,
            location=self.cfg.location,
            project=self.cfg.project,
            website={
                "main_page_suffix": self.cfg.index_document,
                "not_found_page": self.cfg.error_document or self.cfg.index_document
            },
            uniform_bucket_level_access=True,
            force_destroy=True,
            labels={
                "environment": self.cfg.environment.replace('.', '-'),
                "managed-by": "archie"
            }
        )
        
        # 3. Public Access
        factory.create(
            "gcp:storage:BucketIAMBinding",
            f"{self.name}-public-read",
            bucket=self.bucket.name,
            role="roles/storage.objectViewer",
            members=["allUsers"]
        )
        
        # 4. Upload Content — always use FileAsset (content prop unreliable in GCP provider)
        files = self._download_source_files(bucket_name=bucket_name, stack_name=self.name)
        for f in files:
            file_key = f["key"]
            # Write all files to disk (text files may have been customized in memory)
            temp_file = Path(self.temp_dir.name) / file_key
            if not temp_file.exists():
                if isinstance(f["content"], bytes):
                    with open(temp_file, 'wb') as fh:
                        fh.write(f["content"])
                else:
                    with open(temp_file, 'w', encoding='utf-8') as fh:
                        fh.write(f["content"])

            factory.create(
                "gcp:storage:BucketObject",
                f"{self.name}-{file_key.replace('.', '-')}",
                name=file_key,
                bucket=self.bucket.name,
                content_type=f["content_type"],
                source=pulumi.FileAsset(str(temp_file)),
            )

        website_url = pulumi.Output.concat("https://storage.googleapis.com/", self.bucket.name, "/index.html")
        pulumi.export("website_url", website_url)
        pulumi.export("bucket_name", self.bucket.name)
        
        return {
            "template_name": "gcp-static-website",
            "outputs": {
                "bucket_name": self.bucket.name,
                "website_url": website_url
            }
        }

    def get_outputs(self) -> Dict[str, Any]:
        """Get template outputs"""
        if not self.bucket: return {}
        website_url = pulumi.Output.concat("https://storage.googleapis.com/", self.bucket.name, "/index.html")
        return {
            "bucket_name": self.bucket.name,
            "website_url": website_url
        }

    @classmethod
    def get_metadata(cls) -> Dict[str, Any]:
        """Template metadata (Pattern B)"""
        return {
            "name": "gcp-static-website",
            "title": "Demo Static Website",
            "description": "Deploy an Archie-branded congratulations page on Google Cloud Storage - perfect for your first GCP deployment!",
            "category": "website",
            "cloud": "gcp",
            "version": "1.1.0",
            "author": "InnovativeApps",
            "tags": ["gcp", "storage", "website", "static", "free"],
            "base_cost": "$0.00/month",
            "complexity": "low",
            "deployment_time": "2-3 minutes",
            "marketplace_group": "WEBSITES",
            "pillars": [
                {
                    "title": "Operational Excellence",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Managed hosting with minimal operational overhead.",
                    "practices": [
                        "Infrastructure as Code with Pulumi for repeatable deployments",
                        "Automated content upload from versioned source bucket",
                        "Consistent resource labeling for tracking and organization",
                        "Force-destroy enabled for clean teardown in non-production"
                    ]
                },
                {
                    "title": "Security",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Public-read access appropriate for static website hosting.",
                    "practices": [
                        "Uniform bucket-level access for simplified IAM management",
                        "IAM binding scoped to objectViewer role only",
                        "No server-side code execution surface to attack",
                        "HTTPS access via Cloud Storage public URL"
                    ]
                },
                {
                    "title": "Reliability",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Cloud Storage provides highly durable and available hosting.",
                    "practices": [
                        "Google Cloud Storage 99.95% availability SLA",
                        "11 nines durability for stored objects",
                        "Automatic replication across zones within region",
                        "Embedded fallback content if source bucket is unavailable"
                    ]
                },
                {
                    "title": "Performance Efficiency",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "Serverless static hosting with global Google network.",
                    "practices": [
                        "Direct Cloud Storage serving with no compute overhead",
                        "Google global network edge caching for low latency",
                        "Lightweight HTML/CSS assets for fast page loads",
                        "No cold start or server provisioning delays"
                    ]
                },
                {
                    "title": "Cost Optimization",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Near-zero cost for static website hosting on Cloud Storage.",
                    "practices": [
                        "No compute instances or server costs",
                        "Pay only for storage and egress bandwidth",
                        "Free-tier eligible for small sites",
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
                        "Google Cloud carbon-neutral infrastructure",
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
                    "default": "my-gcp-site"
                }
            }
        }

    def cleanup(self) -> None:
        """Clean up temporary files"""
        if self.temp_dir:
            self.temp_dir.cleanup()
