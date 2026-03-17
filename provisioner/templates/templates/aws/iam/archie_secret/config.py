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
                "projectName": {
                    "type": "string",
                    "title": "Project Name",
                    "description": "Unique identifier for this project (e.g., 'myapp')",
                    "order": 1
                },
                "access_key": {
                    "type": "string",
                    "title": "AWS Access Key ID",
                    "description": "The Access Key ID for Archie's service user",
                    "placeholder": "AKIA...",
                    "is_secret": True,
                    "order": 2
                },
                "secret_key": {
                    "type": "string",
                    "title": "AWS Secret Access Key",
                    "description": "The Secret Access Key for Archie's service user",
                    "placeholder": "wJalr...",
                    "is_secret": True,
                    "order": 3
                }
            },
            "required": ["projectName", "access_key", "secret_key"]
        }
