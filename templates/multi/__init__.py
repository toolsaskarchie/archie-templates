"""Multi-Cloud Templates"""
from provisioner.templates.templates.multi.web_app import MultiWebAppTemplate
from provisioner.templates.templates.multi.database import MultiDatabaseTemplate
from provisioner.templates.templates.multi.k8s_app import MultiK8sAppTemplate

__all__ = ["MultiWebAppTemplate", "MultiDatabaseTemplate", "MultiK8sAppTemplate"]
