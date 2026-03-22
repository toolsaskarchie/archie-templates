"""
Free Static Website Template

Deploys an Archie-branded static website to S3 for first-time users.
Downloads HTML/CSS from Archie's source bucket and deploys using S3 components.
"""

from typing import Any, Dict, List, Optional
import tempfile
import boto3
import os
from pathlib import Path
import pulumi
import pulumi_aws as aws

# Import Archie utils for consistent patterns
from provisioner.utils.aws import (
    ResourceNamer,
    get_standard_tags
)
from provisioner.templates.base import template_registry, InfrastructureTemplate
from provisioner.templates.templates.aws.s3.static_website.config import StaticWebsiteConfig
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory


@template_registry("aws-static-website")
class S3StaticWebsiteTemplate(InfrastructureTemplate):
    """
    Free Static Website Template - Pattern B Implementation
    
    Creates:
    - S3 bucket for website hosting
    - Public access configuration
    - Website configuration (index.html, etc.)
    - Bucket policy for public read
    - Website files upload
    
    All resources created via factory pattern.
    """
    
    def __init__(self, name: str = None, config: Dict[str, Any] = None, aws: Dict[str, Any] = None, **kwargs):
        """Initialize free static website template"""
        raw_config = config or aws or kwargs or {}
        self.cfg = StaticWebsiteConfig(raw_config)
        
        if name is None:
            name = raw_config.get('projectName', 'archie-website')
        
        super().__init__(name, raw_config)
        
        self.config = raw_config
        self.temp_dir: Optional[tempfile.TemporaryDirectory] = None
        self.bucket: Optional[aws.s3.Bucket] = None
        
        # Environment settings for source files
        environment = os.getenv("ENVIRONMENT", "sandbox")
        self.SOURCE_BUCKET = f"archie-static-website-source-{environment}"
        self.SOURCE_REGION = "us-east-1"
        self.SOURCE_FILES = ["index-aws.html", "styles.css"]
    
    def _download_source_files(self, bucket_name: str = None, stack_name: str = None) -> List[Dict[str, Any]]:
        """Download branded files from Archie source S3 bucket, fallback to embedded."""
        self.temp_dir = tempfile.TemporaryDirectory()
        temp_path = Path(self.temp_dir.name)

        try:
            s3 = boto3.client("s3", region_name=self.SOURCE_REGION)
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
                        content = f.read()
                else:
                    with open(local_path, 'r', encoding='utf-8') as f:
                        content = f.read()

                downloaded.append({"content": content, "key": deploy_key, "content_type": self._get_content_type(deploy_key)})
            return downloaded
        except Exception as e:
            print(f"[AWS-STATIC-WEBSITE] Fallback to embedded content: {e}")
            return self._get_embedded_files(bucket_name, stack_name)

    def _get_embedded_files(self, bucket_name: str = None, stack_name: str = None) -> List[Dict[str, Any]]:
        """Default content if source bucket is unavailable."""
        import datetime
        ts = datetime.datetime.now().strftime("%B %d, %Y at %I:%M %p UTC")
        html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><title>Deployment Success</title>
<link rel="stylesheet" href="styles.css"></head><body>
<div style="font-family:sans-serif;text-align:center;padding:50px;">
<h1>🎉 Deployment Successful!</h1><p>Your AWS Static Website is live.</p>
<div style="background:#f4f4f4;padding:20px;border-radius:8px;display:inline-block;text-align:left;">
<p><strong>Bucket:</strong> {bucket_name}</p><p><strong>Stack:</strong> {stack_name}</p>
<p><strong>Time:</strong> {ts}</p></div></div></body></html>"""
        css = "body { background: #fafafa; color: #333; }"
        return [
            {"content": html, "key": "index.html", "content_type": "text/html"},
            {"content": css, "key": "styles.css", "content_type": "text/css"},
        ]

    def _get_content_type(self, file_key: str) -> str:
        ext_map = {".html": "text/html", ".css": "text/css", ".png": "image/png", ".jpg": "image/jpeg"}
        return ext_map.get(Path(file_key).suffix, "text/plain")

    def _customize_html(self, html_path: Path, bucket_name: str = None, stack_name: str = None) -> None:
        import datetime
        with open(html_path, 'r', encoding='utf-8') as f:
            content = f.read()

        project_name = (
            self.config.get('parameters', {}).get('aws', {}).get('projectName') or
            self.config.get('projectName') or
            self.name or 'your-project'
        )
        environment = self.cfg.environment or 'nonprod'
        region = self.cfg.region

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
        """Deploy static website using factory pattern (implements abstract method)"""
        return self.create()
    
    def create(self) -> Dict[str, Any]:
        """Deploy static website using factory pattern"""
        
        # Initialize namer
        environment = self.cfg.environment or 'nonprod'
        namer = ResourceNamer(
            project=self.cfg.project_name,
            environment=environment,
            region=self.cfg.region,
            template="aws-static-website"
        )
        
        # Build smart bucket name: archie-guest-{project}-{env}-{region}
        project_name = self.cfg.project_name
        clean_project = (project_name
            .replace('archie-guest-', '')
            .replace('stack-', '')
            .replace('aws-static-website-', '')
            .replace('static-website-s3-', '')
            .replace('demo-', '')
            .lower()
            .replace('_', '-'))
        
        import random, string as _string
        suffix = ''.join(random.choices(_string.ascii_lowercase + _string.digits, k=6))
        # Reuse existing bucket name on upgrade (has random suffix — can't regenerate)
        existing_bucket = self.config.get('s3_bucket_name') or self.config.get('bucket_name')
        if existing_bucket:
            bucket_name = existing_bucket
        else:
            bucket_name = namer.s3_bucket(purpose="website", suffix=clean_project)
            if not bucket_name.startswith("archie-guest"):
                 bucket_name = f"archie-guest-{bucket_name}"
            bucket_name = f"{bucket_name}-{suffix}"
            if len(bucket_name) > 63:
                bucket_name = bucket_name[:63].rstrip('-')
        
        # Standard tags
        tags = get_standard_tags(
            project=project_name,
            environment=environment,
            template="aws-static-website"
        )
        tags.update(self.cfg.tags)
        
        # Download source files
        files = self._download_source_files(bucket_name=bucket_name, stack_name=self.name)
        
        # 1. Create S3 Bucket
        self.bucket = factory.create(
            "aws:s3:Bucket",
            bucket_name,
            bucket=bucket_name,
            force_destroy=True,
            tags={**tags, "Name": bucket_name}
        )
        
        # 2. Public Access Block (Disable to allow website hosting)
        factory.create(
            "aws:s3:BucketPublicAccessBlock",
            f"{self.name}-public-access",
            bucket=self.bucket.id,
            block_public_acls=False,
            block_public_policy=False,
            ignore_public_acls=False,
            restrict_public_buckets=False
        )
        
        # 3. Website Configuration
        factory.create(
            "aws:s3:BucketWebsiteConfigurationV2",
            f"{self.name}-website-config",
            bucket=self.bucket.id,
            index_document={"suffix": "index.html"},
            error_document={"key": "index.html"} # Simple single-page app style
        )
        
        # 4. Bucket Policy
        bucket_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": "*",
                    "Action": "s3:GetObject",
                    "Resource": pulumi.Output.concat(self.bucket.arn, "/*")
                }
            ]
        }
        
        factory.create(
            "aws:s3:BucketPolicy",
            f"{self.name}-bucket-policy",
            bucket=self.bucket.id,
            policy=pulumi.Output.json_dumps(bucket_policy)
        )
        
        # 5. Upload Files
        for file_info in files:
            file_key = file_info["key"]
            file_content = file_info["content"]
            content_type = file_info["content_type"]
            
            resource_name = f"{self.name}-{file_key.replace('.', '-').replace('/', '-')}"
            
            if isinstance(file_content, bytes):
                import tempfile
                import os
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file_key)[1])
                temp_file.write(file_content)
                temp_file.close()
                
                factory.create(
                    "aws:s3:BucketObject",
                    resource_name,
                    bucket=self.bucket.id,
                    key=file_key,
                    source=pulumi.FileAsset(temp_file.name),
                    content_type=content_type
                )
            else:
                factory.create(
                    "aws:s3:BucketObject",
                    resource_name,
                    bucket=self.bucket.id,
                    key=file_key,
                    content=file_content,
                    content_type=content_type
                )
        
        # Outputs
        website_url = pulumi.Output.concat(
            "http://", self.bucket.bucket, ".s3-website-", self.cfg.region, ".amazonaws.com"
        )
        
        pulumi.export("bucket_name", self.bucket.bucket)
        pulumi.export("s3_bucket_name", bucket_name)
        pulumi.export("website_url", website_url)
        return {
            "bucket_name": self.bucket.bucket,
            "website_url": website_url,
            "bucket_arn": self.bucket.arn
        }
    
    def get_outputs(self) -> Dict[str, Any]:
        """Get template outputs"""
        if not self.bucket:
             return {}
        
        website_url = pulumi.Output.concat(
            "http://", self.bucket.bucket, ".s3-website-", self.cfg.region, ".amazonaws.com"
        )
        
        return {
            "bucket_name": self.bucket.bucket,
            "website_url": website_url,
            "bucket_arn": self.bucket.arn
        }
    
    def cleanup(self) -> None:
        """Clean up temporary files"""
        if self.temp_dir:
            self.temp_dir.cleanup()
    
    @classmethod
    def get_metadata(cls) -> Dict[str, Any]:
        """Get template metadata (implements abstract method)"""
        return {
            "name": "aws-static-website",
            "title": "Demo Static Website",
            "description": "Enterprise-grade static website hosting on Amazon S3. Deploys a customized Archie congratulations page with responsive design, dark/light theme support, and zero infrastructure cost within AWS Free Tier.",
            "category": "website",
            "version": "1.0.0",
            "author": "InnovativeApps",
            "cloud": "aws",
            "environment": "nonprod",
            "base_cost": "$0/month",
            "estimated_cost": "$0.00 - $0.50/month (Free Tier Eligible)",
            "deployment_time": "1-2 minutes",
            "complexity": "beginner",
            "tags": ["s3", "website", "static", "free", "beginner-friendly", "aws-static-website"],
            "features": [
                "Instant S3-Backed Web Hosting",
                "Pre-customized Archie Congratulations Page",
                "Automated Public Access Block Management",
                "Secure S3 Bucket Policy Configuration",
                "Zero Infrastructure Cost (AWS Free Tier)",
                "Dark/Light Theme Support with native assets"
            ],
            "use_cases": [
                "First deployment with Archie",
                "Learn S3 static website hosting",
                "Test Archie deployment flow",
                "Static landing pages"
            ],
            "pillars": [
                {
                    "title": "Operational Excellence",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Fully automated deployment with Archie. No server management, updates, or maintenance required.",
                    "practices": [
                        "One-click deployment with Archie",
                        "No server patching or updates needed",
                        "S3 versioning available for rollbacks",
                        "Infrastructure as code for consistency",
                        "Easy content updates via S3 console or CLI"
                    ]
                },
                {
                    "title": "Security",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "S3 bucket configured with public access for static website hosting. Uses bucket policies for controlled public access.",
                    "practices": [
                        "Bucket policy allows public read access only",
                        "Block public access settings configured appropriately",
                        "HTTPS available through CloudFront (optional upgrade)",
                        "No sensitive data in static website content",
                        "IAM controls who can modify bucket contents"
                    ]
                },
                {
                    "title": "Reliability",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "S3 provides 99.99% availability and 99.999999999% durability with automatic AZ replication.",
                    "practices": [
                        "S3 automatically replicates across AZs",
                        "No server maintenance or patching required",
                        "Built-in redundancy and fault tolerance",
                        "Automatic recovery from hardware failures",
                        "Content served from multiple S3 endpoints"
                    ]
                },
                {
                    "title": "Performance Efficiency",
                    "score": "good",
                    "score_color": "#f59e0b",
                    "description": "S3 static website hosting provides good performance for static content. Can be enhanced with CloudFront CDN.",
                    "practices": [
                        "Static content served directly from S3",
                        "Minimal latency for single-region access",
                        "HTML/CSS optimized for fast loading",
                        "Can add CloudFront for edge caching",
                        "No compute overhead - pure storage"
                    ]
                },
                {
                    "title": "Cost Optimization",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "Extremely cost-effective solution. Free tier covers most small websites. Only pay for storage and bandwidth used.",
                    "practices": [
                        "S3 free tier: 5GB storage, 20K GET requests",
                        "Pay only for actual storage used (~$0.023/GB)",
                        "No server costs or compute charges",
                        "Minimal bandwidth costs for small sites",
                        "No minimum fees or commitments"
                    ]
                },
                {
                    "title": "Sustainability",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "S3 is a managed service with AWS optimizing infrastructure efficiency. No dedicated servers means minimal carbon footprint.",
                    "practices": [
                        "Shared infrastructure reduces carbon per user",
                        "AWS optimizes data center efficiency",
                        "No dedicated servers to run 24/7",
                        "Minimal compute resources for static content",
                        "Scales down to zero when not accessed"
                    ]
                }
            ]
        }

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        """Get configuration schema for the UI"""
        schema = {
            "type": "object",
            "required": ["project_name"],
            "properties": {}
        }
        
        # Add Project/Env fields
        schema["properties"].update(get_project_env_schema())
        
        return schema
    
    @classmethod
    def get_diagram(cls) -> Dict[str, Any]:
        """Generate infrastructure diagram for Overview tab"""
        return {
            "title": "S3 Static Website",
            "description": "Simple S3 bucket with static website hosting",
            "layout": "hierarchical",
            "nodes": [
                {"id": "s3", "type": "resource", "label": "S3 Bucket", "subLabel": "Website hosting enabled", "style": {"bgColor": "#E8F5E9", "borderColor": "#4CAF50", "highlight": True}},
                {"id": "policy", "type": "resource", "label": "Bucket Policy", "subLabel": "Public read access", "style": {"bgColor": "#F3E5F5", "borderColor": "#AB47BC"}},
                {"id": "files", "type": "group", "label": "Website Files", "style": {"borderColor": "#FF9800", "bgColor": "#FFF3E0"}, "children": [
                    {"id": "html", "type": "resource", "label": "index.html", "subLabel": "Main page"},
                    {"id": "css", "type": "resource", "label": "styles.css", "subLabel": "Styling"},
                    {"id": "logo", "type": "resource", "label": "archie-logo.png", "subLabel": "Brand logo"}
                ]},
                {"id": "url", "type": "resource", "label": "Website URL", "subLabel": "HTTP endpoint", "style": {"bgColor": "#E3F2FD", "borderColor": "#1976D2"}}
            ],
            "connections": [
                {"id": "c1", "source": "s3", "target": "policy", "label": "has", "type": "reference"},
                {"id": "c2", "source": "s3", "target": "html", "label": "hosts", "type": "hierarchy"},
                {"id": "c3", "source": "s3", "target": "css", "label": "hosts", "type": "hierarchy"},
                {"id": "c4", "source": "s3", "target": "logo", "label": "hosts", "type": "hierarchy"},
                {"id": "c5", "source": "url", "target": "s3", "label": "serves from", "type": "reference", "style": {"color": "#1976D2", "animated": True}}
            ]
        }
    
    @classmethod
    def get_template_info(cls) -> Dict[str, Any]:
        """Get template metadata"""
        return {
            "name": "aws-static-website",
            "title": "Free Static Website",
            "description": "Enterprise-grade static website hosting solution that deploys a fully-customized Archie congratulations page on Amazon S3, designed specifically for your first AWS infrastructure deployment. This template automatically creates an S3 bucket with static website hosting enabled, configures public read access with proper security boundaries, and deploys a professionally designed landing page featuring Archie's branding, deployment details, and responsive design with dark/light theme support. The website includes your project name, deployment timestamp, environment details, and region information dynamically injected during deployment. Built using Infrastructure-as-Code principles with Pulumi, this template demonstrates secure S3 bucket policy configuration, automated public access block management, and zero infrastructure cost operation within AWS Free Tier limits. Perfect for testing deployment workflows, showcasing successful infrastructure automation, or serving as a foundation for more complex static website architectures.",
            "category": "website",
            "complexity": "low",
            "cost_tier": "free",
            "use_cases": [
                "First deployment with Archie",
                "Learn S3 static website hosting",
                "Test Archie deployment flow"
            ],
            "features": [
                "S3 bucket with website hosting",
                "Archie-branded congratulations page",
                "Dark/light theme support",
                "Public access configured",
                "Zero cost (free tier eligible)"
            ],
            "estimated_cost": "$0.00 - $0.50/month (S3 free tier: 5GB storage, 20K GET requests)",
            "deployment_time": "1-2 minutes",
            "required_config": [],
            "optional_config": [
                "bucket_name - Custom bucket name (default: auto-generated)",
                "tags - Resource tags"
            ],
            "tags": [
                "s3", "website", "static", "free", "beginner-friendly"
            ],
            "outputs": [
                "website_url - The URL to visit your congratulations page",
                "bucket_name - The S3 bucket name",
                "bucket_arn - The bucket ARN"
            ],
            "next_steps": [
                "Visit the website URL to see your page",
                "Connect your AWS account for more advanced deployments",
                "Browse the Archie marketplace for more templates"
            ]
        }
