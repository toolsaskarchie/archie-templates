"""Configuration for Archie Secret Template."""
from typing import Optional, Dict, Any, List
from pathlib import Path

from provisioner.utils.config_loader import TemplateConfigLoader


class ArchieSecretConfig:
    """Configuration for Archie Secret template.
    
    Loads defaults from defaults.yaml and handles UI-configurable parameters.
    """
    
    def __init__(self, raw_config: Dict[str, Any]):
        self.raw_config = raw_config
        params = self.raw_config.get('parameters', {})
        self.parameters = params.get('aws', {}) or params
        
        # Load defaults from YAML
        template_dir = Path(__file__).parent
        self.config_loader = TemplateConfigLoader(template_dir)
        self.defaults = self.config_loader.config
        
        # Metadata
        self.environment = self.raw_config.get('environment', 'nonprod')
        self.region = self.raw_config.get('region', 'us-east-1')
        self.tags = self.raw_config.get('tags', {})
        self.region = self.raw_config.get('region', 'us-east-1')
        
        # Project Name
        self.project_name = (
            self.parameters.get('projectName') or
            self.parameters.get('project_name') or
            self.raw_config.get('projectName') or
            self.raw_config.get('project_name') or
            'archie'
        )

    @property
    def secret_name(self) -> str:
        """Get secret name generated from project/env."""
        prefix = self.config_loader.get('secret.name_prefix', 'archie/credentials')
        return f"{prefix}/{self.project_name}/{self.environment}"

    @property
    def access_key(self) -> Optional[str]:
        """AWS Access Key ID from parameters."""
        return self.parameters.get('access_key')

    @property
    def secret_key(self) -> Optional[str]:
        """AWS Secret Access Key from parameters."""
        return self.parameters.get('secret_key')

    @staticmethod
    def get_config_schema() -> Dict[str, Any]:
        """Get JSON schema for UI configuration."""
        return {
            "type": "object",
            "properties": {
                "essentials_header": {
                    "type": "separator",
                    "title": "Template Essentials",
                    "group": "Essentials",
                    "isEssential": True,
                    "order": 0
                },
                "projectName": {
                    "type": "string",
                    "title": "Project Name",
                    "description": "Unique identifier for this project (e.g., 'myapp')",
                    "group": "Essentials",
                    "isEssential": True,
                    "order": 1
                },
                "keys_header": {
                    "type": "separator",
                    "title": "Keys to Store",
                    "description": "These credentials will be securely stored in AWS Secrets Manager.",
                    "group": "Keys to Store",
                    "isEssential": True,
                    "order": 10
                },
                "access_key": {
                    "type": "string",
                    "title": "Access Key ID to Store",
                    "description": "The Access Key ID that Archie will use for deployments (stored in Secrets Manager)",
                    "placeholder": "AKIA...",
                    "is_secret": True,
                    "group": "Keys to Store",
                    "isEssential": True,
                    "order": 11
                },
                "secret_key": {
                    "type": "string",
                    "title": "Secret Access Key to Store",
                    "description": "The Secret Access Key that Archie will use for deployments (stored in Secrets Manager)",
                    "placeholder": "wJalr...",
                    "is_secret": True,
                    "group": "Keys to Store",
                    "isEssential": True,
                    "order": 12
                },
                "team_name": {
                    "type": "string",
                    "default": "",
                    "title": "Team Name",
                    "description": "Team that owns this resource",
                    "order": 50,
                    "group": "Tags",
                },
            },
            "required": ["projectName", "access_key", "secret_key"]
        }
