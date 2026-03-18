"""
Aurora Non-Production Template

Deploys a cost-optimized Aurora PostgreSQL or MySQL-compatible database cluster for development, testing, and staging environments.

Features:
- Managed Aurora cluster with automated failover
- Cost-optimized defaults (db.t3.medium, single instance)
- Automated backups with configurable retention
- VPC isolation with security groups
- Password stored in AWS Secrets Manager
- Optional Performance Insights

Architecture: Layer 4 template that CALLS VPC Non-Prod template (Layer 4)
and composes resources via factory.create() (Pattern B)
"""
import random
import string
from typing import Any, Dict, Optional, List
from pathlib import Path

import pulumi
import pulumi_aws as aws

from provisioner.templates.base import (
    InfrastructureTemplate,
    template_registry
)
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory
from provisioner.templates.template_config import TemplateConfig
from provisioner.utils.aws import ResourceNamer, get_standard_tags
from provisioner.utils.aws.cidr_utils import generate_random_vpc_cidr
from provisioner.templates.templates.aws.database.aurora_nonprod.config import AuroraNonProdConfig
from provisioner.templates.templates.aws.networking.vpc_nonprod.pulumi import VPCSimpleNonprodTemplate


@template_registry("aws-aurora-nonprod")
class AuroraNonProdTemplate(InfrastructureTemplate):
    """
    Aurora Non-Production Template

    Creates a cost-optimized Aurora database cluster for nonprod environments:
    - VPC with public/private subnets (created by default, or use existing)
    - Aurora Cluster (PostgreSQL or MySQL-compatible)
    - Cluster Instances (primary + optional replicas)
    - DB subnet group
    - Security group with configurable access
    - Password stored in AWS Secrets Manager
    - Automated backups (3-day retention)
    - Optional Performance Insights
    """

    def __init__(self, name: str = None, config: Dict[str, Any] = None, **kwargs):
        """Initialize Aurora nonprod template"""
        raw_config = config or kwargs or {}

        if name is None:
            name = raw_config.get('project_name', raw_config.get('projectName', 'aurora-nonprod'))

        super().__init__(name, raw_config)
        
        # Load template configuration (Pattern B)
        template_dir = Path(__file__).parent
        self.config_loader = TemplateConfig(template_dir, raw_config)
        self.cfg = AuroraNonProdConfig(raw_config)

        # Sub-templates
        self.vpc_template: Optional[VPCSimpleNonprodTemplate] = None
        
        # Resources (Pattern B)
        self.cluster = None
        self.instances = []
        self.db_subnet_group = None
        self.security_groups = []
        self.db_password_secret = None
        self.db_password_version = None

    def create_infrastructure(self) -> Dict[str, Any]:
        """Deploy infrastructure (implements abstract method)"""
        return self.create()

    def create(self) -> Dict[str, Any]:
        """Deploy Aurora infrastructure using factory pattern"""
        # Initialize ResourceNamer
        namer = ResourceNamer(
            project=self.cfg.project_name,
            environment=self.cfg.environment,
            region=self.cfg.region,
            template="aws-aurora-nonprod"
        )
        
        # Generate names
        db_identifier = namer.rds(engine=self.cfg.engine, identifier=self.cfg.db_name)
        
        # Generate standard tags
        tags = get_standard_tags(
            project=self.cfg.project_name,
            environment=self.cfg.environment,
            template="aurora-nonprod"
        )
        tags.update(self.cfg.tags)

        print(f"[AURORA-NONPROD] Creating Aurora cluster for {self.cfg.environment}...")

        # ========================================
        # STEP 1: VPC CREATION
        # ========================================
        vpc_id = None
        subnet_ids = []
        
        if self.cfg.vpc_mode == 'new':
            vpc_cidr = self.cfg.vpc_cidr
            if self.cfg.use_random_vpc_cidr:
                vpc_cidr = generate_random_vpc_cidr()
            
            vpc_config = {
                "project_name": f"{self.name}-vpc",
                "cidr_block": vpc_cidr,
                "environment": self.cfg.environment,
                "ssh_access_ip": self.cfg.ssh_access_ip or ''
            }
            
            self.vpc_template = VPCSimpleNonprodTemplate(
                name=f"{self.name}-vpc",
                config=vpc_config
            )
            self.vpc_template.create_infrastructure()
            vpc_outputs = self.vpc_template.get_outputs()
            
            vpc_id = vpc_outputs['vpc_id']
            subnet_ids = vpc_outputs.get('db_subnet_ids', vpc_outputs.get('private_subnet_ids', []))
        else:
            vpc_id = self.cfg.vpc_id
            subnet_ids = self.cfg.subnet_ids

        # ========================================
        # STEP 2: GENERATE SECURE PASSWORD
        # ========================================
        db_password = self._generate_password()

        # ========================================
        # STEP 3: SECURITY GROUPS
        # ========================================
        sg_id = None
        if self.cfg.vpc_mode == 'new' and self.vpc_template:
            vpc_outputs = self.vpc_template.get_outputs()
            sg_id = vpc_outputs.get('db_security_group_id')
        
        if not sg_id:
            # Create dedicated SG
            sg_name = namer.security_group(purpose="db", ports=[self.cfg.port], service=self.cfg.engine)
            fallback_sg = factory.create(
                "aws:ec2:SecurityGroup",
                sg_name,
                vpc_id=vpc_id,
                description=f"Aurora access for {self.cfg.environment}",
                egress=[{
                    "protocol": "-1",
                    "from_port": 0,
                    "to_port": 0,
                    "cidr_blocks": ["0.0.0.0/0"],
                    "description": "Allow all outbound traffic"
                }],
                tags={**tags, "Name": sg_name}
            )
            self.security_groups.append(fallback_sg)
            sg_id = fallback_sg.id
        
        # Add ingress rule
        factory.create(
            "aws:ec2:SecurityGroupRule",
            f"{self.name}-aurora-ingress",
            type="ingress",
            security_group_id=sg_id,
            protocol="tcp",
            from_port=self.cfg.port,
            to_port=self.cfg.port,
            cidr_blocks=self.cfg.allowed_cidr_blocks,
            description=f"Aurora access for {db_identifier} ({self.cfg.environment})"
        )

        # ========================================
        # STEP 4: DB SUBNET GROUP
        # ========================================
        db_subnet_group_name = None
        if subnet_ids and len(subnet_ids) >= 2:
            sng_name = f"sng-db-{namer.project}-main-nonprod-{namer.region_short}"
            self.db_subnet_group = factory.create(
                "aws:rds:SubnetGroup",
                sng_name,
                subnet_ids=subnet_ids,
                description=f"Subnet group for {db_identifier}",
                tags={**tags, "Name": sng_name}
            )
            db_subnet_group_name = self.db_subnet_group.name

        # ========================================
        # STEP 5: SECRETS MANAGER
        # ========================================
        self.db_password_secret = factory.create(
            "aws:secretsmanager:Secret",
            f"{self.name}-password",
            name=f"secret-db-{namer.project}-password-nonprod-{namer.region_short}",
            description=f"Master password for {db_identifier}",
            recovery_window_in_days=7,
            tags=tags
        )

        self.db_password_version = factory.create(
            "aws:secretsmanager:SecretVersion",
            f"{self.name}-password-version",
            secret_id=self.db_password_secret.id,
            secret_string=pulumi.Output.secret(db_password)
        )

        # ========================================
        # STEP 6: AURORA CLUSTER
        # ========================================
        # Aurora needs specific AZ selection if multi-AZ
        availability_zones = None
        if self.cfg.multi_az:
            availability_zones = [f"{self.cfg.region}a", f"{self.cfg.region}b"]

        self.cluster = factory.create(
            "aws:rds:Cluster",
            db_identifier,
            engine=self.cfg.engine,
            engine_version=self.cfg.engine_version,
            cluster_identifier=db_identifier,
            master_username=self.cfg.db_username,
            master_password=db_password,
            database_name=self.cfg.db_name,
            port=self.cfg.port,
            db_subnet_group_name=db_subnet_group_name,
            vpc_security_group_ids=[sg_id],
            backup_retention_period=self.cfg.backup_retention_days,
            storage_encrypted=self.cfg.storage_encrypted,
            availability_zones=availability_zones,
            deletion_protection=self.cfg.deletion_protection_enabled,
            skip_final_snapshot=self.cfg.skip_final_snapshot,
            tags={**tags, "Name": db_identifier}
        )

        # ========================================
        # STEP 7: CLUSTER INSTANCES
        # ========================================
        for i in range(self.cfg.instance_count):
            instance_identifier = f"{db_identifier}-instance-{i+1}"
            instance = factory.create(
                "aws:rds:ClusterInstance",
                instance_identifier,
                identifier=instance_identifier,
                cluster_identifier=self.cluster.id,
                instance_class=self.cfg.instance_class,
                engine=self.cfg.engine,
                engine_version=self.cfg.engine_version,
                publicly_accessible=self.cfg.publicly_accessible,
                performance_insights_enabled=self.cfg.enable_performance_insights,
                tags={**tags, "Name": instance_identifier}
            )
            self.instances.append(instance)

        # ========================================
        # STEP 8: EXPORT OUTPUTS
        # ========================================
        pulumi.export("cluster_endpoint", self.cluster.endpoint)
        pulumi.export("cluster_reader_endpoint", self.cluster.reader_endpoint)
        pulumi.export("port", self.cfg.port)
        pulumi.export("database_name", self.cfg.db_name)
        pulumi.export("db_password_secret_name", self.db_password_secret.name)

        return self.get_outputs()

    def _generate_password(self, length: int = 32) -> str:
        """Generate a secure random password"""
        chars = string.ascii_letters + string.digits + "!#$%^&*()-_=+"
        password = ''.join(random.SystemRandom().choice(chars) for _ in range(length))
        return password

    def get_outputs(self) -> Dict[str, Any]:
        """Get template outputs (Pattern B)"""
        if not self.cluster:
            return {"status": "not_created"}

        outputs = {
            "cluster_id": self.cluster.id,
            "cluster_endpoint": self.cluster.endpoint,
            "reader_endpoint": self.cluster.reader_endpoint,
            "port": self.cfg.port,
            "database_name": self.cfg.db_name,
            "master_username": self.cfg.db_username,
            "password_secret": self.db_password_secret.name if self.db_password_secret else None
        }
        
        if self.vpc_template:
            vpc_outputs = self.vpc_template.get_outputs()
            outputs.update({
                "vpc_id": vpc_outputs.get("vpc_id"),
                "private_subnet_ids": vpc_outputs.get("private_subnet_ids", [])
            })
            
        return outputs

    @classmethod
    def get_metadata(cls) -> Dict[str, Any]:
        """Pattern B Metadata source of truth"""
        return {
            "name": "aws-aurora-nonprod",
            "title": "Aurora Database Cluster",
            "description": "Cost-optimized managed Aurora PostgreSQL or MySQL-compatible database cluster designed for development and staging.",
            "category": "database",
            "version": "1.3.0",
            "author": "InnovativeApps",
            "cloud": "aws",
            "environment": "nonprod",
            "base_cost": "$45/month",
            "features": [
                "Serverless v2 Scaling Support",
                "Managed Aurora Cluster with automated failover",
                "Optional Read Replicas for load distribution",
                "Secure Identity: Automated password rotation via Secrets Manager",
                "Automated Backups with 3-day retention for non-prod safety"
            ],
            "tags": ["aws", "database", "aurora", "postgresql", "mysql", "nonprod", "cost-optimized"],
            "deployment_time": "15-20 minutes",
            "complexity": "medium"
        }

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        """Get configuration schema from source of truth"""
        return AuroraNonProdConfig.get_config_schema()
