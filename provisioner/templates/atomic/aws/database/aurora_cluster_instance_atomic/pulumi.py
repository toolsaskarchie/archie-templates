"""
AWS Aurora Cluster Instance Template
Creates an AWS Aurora cluster instance using direct Pulumi resources.
"""
from typing import Any, Dict, Optional
import pulumi
import pulumi_aws as aws

from provisioner.templates.base import template_registry, InfrastructureTemplate
from .config import AuroraClusterInstanceAtomicConfig
from provisioner.utils.aws import get_standard_tags


@template_registry("aws-aurora-cluster-instance-atomic")
class AuroraClusterInstanceAtomicTemplate(InfrastructureTemplate):
    """
    AWS Aurora Cluster Instance Template
    Creates an instance within an Aurora cluster
    """
    
    def __init__(self, name: str = None, config: Dict[str, Any] = None, **kwargs):
        raw_config = config or kwargs or {}
        self.cfg = AuroraClusterInstanceAtomicConfig(raw_config)
        
        if name is None:
            name = self.cfg.identifier
            
        super().__init__(name, raw_config)
        self.instance: Optional[aws.rds.ClusterInstance] = None

    def create_infrastructure(self) -> Dict[str, Any]:
        """Create Aurora Cluster Instance using direct Pulumi resources"""
        tags = get_standard_tags(
            project=self.cfg.project_name,
            environment=self.cfg.environment,
            template="aurora-cluster-instance-atomic"
        )
        
        # Build instance arguments
        instance_args = {
            "identifier": self.cfg.identifier,
            "cluster_identifier": self.cfg.cluster_identifier,
            "instance_class": self.cfg.instance_class,
            "engine": self.cfg.engine,
            "engine_version": self.cfg.engine_version,
            "publicly_accessible": self.cfg.publicly_accessible,
            "availability_zone": self.cfg.availability_zone,
            "performance_insights_enabled": self.cfg.performance_insights_enabled,
            "performance_insights_retention_period": self.cfg.performance_insights_retention_period,
            "monitoring_interval": self.cfg.monitoring_interval,
            "monitoring_role_arn": self.cfg.monitoring_role_arn,
            "preferred_maintenance_window": self.cfg.preferred_maintenance_window,
            "auto_minor_version_upgrade": self.cfg.auto_minor_version_upgrade,
            "apply_immediately": self.cfg.apply_immediately,
            "tags": {**tags, "Name": self.cfg.identifier}
        }
        
        # Remove None values
        instance_args = {k: v for k, v in instance_args.items() if v is not None}
        
        # Add extra args
        instance_args.update(self.cfg.extra_args)
        
        # Create Aurora cluster instance
        self.instance = aws.rds.ClusterInstance(
            self.name,
            **instance_args
        )
        
        pulumi.export("instance_id", self.instance.id)
        pulumi.export("instance_endpoint", self.instance.endpoint)
        
        return self.get_outputs()

    def get_outputs(self) -> Dict[str, Any]:
        if not self.instance:
            return {}
        return {
            "instance_id": self.instance.id,
            "instance_arn": self.instance.arn,
            "instance_identifier": self.instance.identifier,
            "instance_endpoint": self.instance.endpoint,
            "instance_port": self.instance.port,
            "writer": self.instance.writer,
            "availability_zone": self.instance.availability_zone
        }

    @classmethod
    def get_metadata(cls) -> 'TemplateMetadata':
        from provisioner.templates.base.template import TemplateMetadata, TemplateCategory
        return TemplateMetadata(
            name="aws-aurora-cluster-instance-atomic",
            title="Aurora Cluster Instance",
            description="AWS Aurora cluster instance resource.",
            category=TemplateCategory.DATABASE,
            author="InnovativeApps",
            version="1.0.0",
            tags=["aws", "database", "aurora", "atomic"],
            estimated_cost="N/A",
            complexity="low",
            deployment_time="5-10 minutes"
        )
