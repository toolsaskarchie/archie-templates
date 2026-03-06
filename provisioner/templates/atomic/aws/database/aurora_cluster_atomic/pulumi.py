"""
AWS Aurora Cluster Template
Creates an AWS Aurora database cluster using direct Pulumi resources.
"""
from typing import Any, Dict, Optional
import pulumi
import pulumi_aws as aws

from provisioner.templates.base import template_registry, InfrastructureTemplate
from .config import AuroraClusterAtomicConfig
from provisioner.utils.aws import get_standard_tags


@template_registry("aws-aurora-cluster-atomic")
class AuroraClusterAtomicTemplate(InfrastructureTemplate):
    """
    AWS Aurora Cluster Template
    Creates a managed Aurora cluster (PostgreSQL or MySQL-compatible)
    """
    
    def __init__(self, name: str = None, config: Dict[str, Any] = None, **kwargs):
        raw_config = config or kwargs or {}
        self.cfg = AuroraClusterAtomicConfig(raw_config)
        
        if name is None:
            name = self.cfg.cluster_identifier
            
        super().__init__(name, raw_config)
        self.cluster: Optional[aws.rds.Cluster] = None

    def create_infrastructure(self) -> Dict[str, Any]:
        """Create Aurora Cluster using direct Pulumi resources"""
        tags = get_standard_tags(
            project=self.cfg.project_name,
            environment=self.cfg.environment,
            template="aurora-cluster-atomic"
        )
        
        # Build cluster arguments
        cluster_args = {
            "cluster_identifier": self.cfg.cluster_identifier,
            "engine": self.cfg.engine,
            "engine_version": self.cfg.engine_version,
            "engine_mode": self.cfg.engine_mode,
            "master_username": self.cfg.master_username,
            "master_password": self.cfg.master_password,
            "database_name": self.cfg.database_name,
            "port": self.cfg.port,
            "db_subnet_group_name": self.cfg.db_subnet_group_name,
            "vpc_security_group_ids": self.cfg.vpc_security_group_ids,
            "backup_retention_period": self.cfg.backup_retention_period,
            "preferred_backup_window": self.cfg.preferred_backup_window,
            "preferred_maintenance_window": self.cfg.preferred_maintenance_window,
            "storage_encrypted": self.cfg.storage_encrypted,
            "kms_key_id": self.cfg.kms_key_id,
            "availability_zones": self.cfg.availability_zones,
            "deletion_protection": self.cfg.deletion_protection,
            "skip_final_snapshot": self.cfg.skip_final_snapshot,
            "final_snapshot_identifier": self.cfg.final_snapshot_identifier,
            "apply_immediately": self.cfg.apply_immediately,
            "enabled_cloudwatch_logs_exports": self.cfg.enabled_cloudwatch_logs_exports,
            "tags": {**tags, "Name": self.cfg.cluster_identifier}
        }
        
        # Remove None values
        cluster_args = {k: v for k, v in cluster_args.items() if v is not None}
        
        # Add extra args
        cluster_args.update(self.cfg.extra_args)
        
        # Create Aurora cluster
        self.cluster = aws.rds.Cluster(
            self.name,
            **cluster_args
        )
        
        pulumi.export("cluster_id", self.cluster.id)
        pulumi.export("cluster_endpoint", self.cluster.endpoint)
        pulumi.export("cluster_reader_endpoint", self.cluster.reader_endpoint)
        
        return self.get_outputs()

    def get_outputs(self) -> Dict[str, Any]:
        if not self.cluster:
            return {}
        return {
            "cluster_id": self.cluster.id,
            "cluster_arn": self.cluster.arn,
            "cluster_identifier": self.cluster.cluster_identifier,
            "cluster_endpoint": self.cluster.endpoint,
            "cluster_reader_endpoint": self.cluster.reader_endpoint,
            "cluster_port": self.cluster.port,
            "cluster_resource_id": self.cluster.cluster_resource_id,
            "hosted_zone_id": self.cluster.hosted_zone_id
        }

    @classmethod
    def get_metadata(cls) -> 'TemplateMetadata':
        from provisioner.templates.base.template import TemplateMetadata, TemplateCategory
        return TemplateMetadata(
            name="aws-aurora-cluster-atomic",
            title="Aurora Cluster",
            description="AWS Aurora database cluster resource.",
            category=TemplateCategory.DATABASE,
            author="InnovativeApps",
            version="1.0.0",
            tags=["aws", "database", "aurora", "atomic"],
            estimated_cost="N/A",
            complexity="medium",
            deployment_time="10-15 minutes"
        )
