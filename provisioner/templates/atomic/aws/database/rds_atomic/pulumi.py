"""
AWS RDS Instance Template
Creates a standalone AWS RDS Instance using the RDSInstanceComponent.
"""
from typing import Any, Dict, Optional
import pulumi

from provisioner.templates.base import template_registry, InfrastructureTemplate
import pulumi_aws as aws
from .config import RDSInstanceAtomicConfig
from provisioner.utils.aws import get_standard_tags

@template_registry("aws-rds-atomic")
class RDSInstanceAtomicTemplate(InfrastructureTemplate):
    """
    AWS RDS Instance Template
    """
    
    def __init__(self, name: str = None, config: Dict[str, Any] = None, **kwargs):
        raw_config = config or kwargs or {}
        self.cfg = RDSInstanceAtomicConfig(raw_config)
        
        if name is None:
            name = self.cfg.identifier
            
        super().__init__(name, raw_config)
        self.db: Optional[aws.rds.Instance] = None

    def create_infrastructure(self) -> Dict[str, Any]:
        """Create RDS Instance using RDSInstanceComponent"""
        tags = get_standard_tags(
            project=self.cfg.project_name,
            environment=self.cfg.environment,
            template="rds-atomic"
        )
        
        self.db = aws.rds.Instance(
            self.name,
            identifier=self.cfg.identifier,
            engine=self.cfg.engine,
            engine_version=self.cfg.engine_version,
            instance_class=self.cfg.instance_class,
            allocated_storage=self.cfg.allocated_storage,
            username=self.cfg.username,
            password=self.cfg.password,
            db_subnet_group_name=self.cfg.db_subnet_group_name,
            vpc_security_group_ids=self.cfg.vpc_security_group_ids,
            tags={**tags, "Name": self.cfg.identifier},
            **self.cfg.extra_args
        )
        
        pulumi.export("db_instance_id", self.db.id)
        pulumi.export("db_endpoint", self.db.endpoint)
        
        return self.get_outputs()

    def get_outputs(self) -> Dict[str, Any]:
        if not self.db:
            return {}
        return {
            "db_instance_id": self.db.id,
            "db_instance_arn": self.db.arn,
            "db_endpoint": self.db.endpoint,
            "db_address": self.db.address,
            "db_port": self.db.port
        }

    @classmethod
    def get_metadata(cls):
        return {
            "name": "rds-atomic",
            "title": "RDS Instance",
            "description": "Standalone AWS RDS Instance resource.",
            "category": "database",
            "provider": "aws",
            "tier": "atomic"
        }
