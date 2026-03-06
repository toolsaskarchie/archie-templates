"""
Azure App Service Container Web App Template - Pattern B Implementation

Deploys an Archie-branded congratulations page as a containerized web app on Azure App Service.
Uses PulumiAtomicFactory for resource creation and standardized metadata.
"""

from typing import Any, Dict, List, Optional
import tempfile
import boto3
import os
import base64
import random
import string
from pathlib import Path
import pulumi

from provisioner.templates.base import template_registry, InfrastructureTemplate
from .config import AzureContainerWebAppConfig
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory


@template_registry("azure-container-webapp")
class AzureContainerWebAppTemplate(InfrastructureTemplate):
    """
    Azure Container Web App Template
    
    Creates:
    - Azure Resource Group
    - Azure App Service Plan
    - Azure App Service (Linux with Docker container)
    """
    
    def __init__(self, name: str = None, config: Dict[str, Any] = None, **kwargs):
        """Initialize Azure container web app template"""
        raw_config = config or kwargs or {}
        if name is None:
            name = raw_config.get('appName', 'azure-webapp')
        super().__init__(name, raw_config)
        self.cfg = AzureContainerWebAppConfig(raw_config)
        self.temp_dir: Optional[tempfile.TemporaryDirectory] = None
        self.resource_group = None
        self.app_service_plan = None
        self.app_service = None
        
        environment = os.getenv("ENVIRONMENT", "sandbox")
        self.SOURCE_BUCKET = f"archie-static-website-source-{environment}"
        self.SOURCE_REGION = "us-east-1"
        self.SOURCE_FILES = ["index.html", "styles.css"]
    
    def _download_source_files(self, app_service_name: str = None, stack_name: str = None) -> List[Dict[str, Any]]:
        """Download and customize files from S3"""
        self.temp_dir = tempfile.TemporaryDirectory()
        temp_path = Path(self.temp_dir.name)
        s3_client = boto3.client("s3", region_name=self.SOURCE_REGION)
        
        downloaded_files = []
        for file_key in self.SOURCE_FILES:
            try:
                local_path = temp_path / file_key
                s3_client.download_file(self.SOURCE_BUCKET, file_key, str(local_path))
                
                if file_key == "index.html":
                    self._customize_html(local_path, app_service_name=app_service_name, stack_name=stack_name)
                
                with open(local_path, 'r', encoding='utf-8') as f:
                    file_content = f.read()
                
                content_type = "text/html" if file_key.endswith(".html") else "text/css"
                downloaded_files.append({"content": file_content, "key": file_key, "content_type": content_type})
            except Exception as e:
                print(f"[AZURE-WEBAPP] Failed to download {file_key}: {e}")
                raise
        return downloaded_files
    
    def _customize_html(self, html_path: Path, app_service_name: str = None, stack_name: str = None) -> None:
        """Inject variables into HTML"""
        import datetime
        with open(html_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        replacements = {
            '{{DEPLOYMENT_NAME}}': stack_name or self.name,
            '{{APP_SERVICE_NAME}}': app_service_name or "unknown",
            '{{TIMESTAMP}}': datetime.datetime.now().strftime("%B %d, %Y at %I:%M %p UTC"),
            '{{LOGO_URL}}': f"https://{self.SOURCE_BUCKET}.s3.{self.SOURCE_REGION}.amazonaws.com/archie-logo.png"
        }
        
        for k, v in replacements.items():
            content = content.replace(k, str(v))
            
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(content)

    def create_infrastructure(self) -> Dict[str, Any]:
        """Deploy infrastructure using factory pattern"""
        random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
        safe_project = ''.join(c for c in self.name.lower() if c.isalnum())[:20]
        app_service_name = f"{safe_project}-app-{random_suffix}"
        
        # 1. Content Preparation
        files = self._download_source_files(app_service_name=app_service_name, stack_name=self.name)
        html_b64 = base64.b64encode(next(f['content'] for f in files if f['key'] == 'index.html').encode('utf-8')).decode('utf-8')
        css_b64 = base64.b64encode(next(f['content'] for f in files if f['key'] == 'styles.css').encode('utf-8')).decode('utf-8')
        
        # 2. Resource Group
        self.resource_group = factory.create(
            "azure-native:resources:ResourceGroup",
            f"{self.name}-rg",
            resource_group_name=self.cfg.resourceGroup or f"rg-{safe_project}-{random_suffix}",
            location=self.cfg.location,
            tags={"ManagedBy": "Archie"}
        )
        
        # 3. App Service Plan
        self.app_service_plan = factory.create(
            "azure-native:web:AppServicePlan",
            f"{self.name}-plan",
            name=f"plan-{safe_project}-{random_suffix}",
            resource_group_name=self.resource_group.name,
            location=self.cfg.location,
            kind="Linux",
            reserved=True,
            sku={"name": "F1", "tier": "Free"},
            tags={"ManagedBy": "Archie"}
        )
        
        # 4. Web App
        from pulumi_azure_native import web
        self.app_service = factory.create(
            "azure-native:web:WebApp",
            f"{self.name}-app",
            name=app_service_name,
            resource_group_name=self.resource_group.name,
            location=self.cfg.location,
            server_farm_id=self.app_service_plan.id,
            https_only=True,
            site_config=web.SiteConfigArgs(
                linux_fx_version="DOCKER|nginx:alpine",
                app_settings=[
                    web.NameValuePairArgs(name="ARCHIE_HTML_B64", value=html_b64),
                    web.NameValuePairArgs(name="ARCHIE_CSS_B64", value=css_b64),
                ],
                app_command_line=(
                    "sh -c 'echo \"$ARCHIE_HTML_B64\" | base64 -d > /usr/share/nginx/html/index.html && "
                    "echo \"$ARCHIE_CSS_B64\" | base64 -d > /usr/share/nginx/html/styles.css && "
                    "nginx -g \"daemon off;\"'"
                ),
            ),
            tags={"ManagedBy": "Archie"}
        )
        
        website_url = pulumi.Output.concat("https://", self.app_service.default_host_name)
        pulumi.export("website_url", website_url)
        
        return {
            "template_name": "azure-container-webapp",
            "outputs": {
                "app_service_name": self.app_service.name,
                "website_url": website_url
            }
        }

    def get_outputs(self) -> Dict[str, Any]:
        """Get template outputs"""
        if not self.app_service: return {}
        return {
            "app_service_name": self.app_service.name,
            "website_url": pulumi.Output.concat("https://", self.app_service.default_host_name)
        }

    def cleanup(self) -> None:
        """Clean up temporary files"""
        if self.temp_dir: self.temp_dir.cleanup()

    @classmethod
    def get_metadata(cls) -> Dict[str, Any]:
        """Template metadata (Pattern B)"""
        return {
            "name": "azure-container-webapp",
            "title": "Container Web App",
            "description": "Deploy an Archie-branded congratulations page as a containerized web app on Azure App Service.",
            "category": "compute",
            "cloud": "azure",
            "version": "1.1.0",
            "author": "InnovativeApps",
            "tags": ["azure", "app-service", "container", "docker", "webapp"],
            "base_cost": "$0.00/month (Free Tier)",
            "complexity": "low",
            "deployment_time": "5-7 minutes",
            "marketplace_group": "WEBSITES"
        }
    
    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        """Get configuration schema"""
        return {
            "type": "object",
            "properties": {
                "appName": {
                    "type": "string",
                    "title": "App Name",
                    "default": "my-azure-app"
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
            "required": ["appName", "resourceGroup"]
        }
