"""
RDS PostgreSQL Non-Production Template

Deploys a cost-optimized PostgreSQL database for development, testing, and staging environments.

Features:
- Cost-optimized defaults (db.t3.micro, 20GB storage)
- Auto-scaling storage up to specified limit
- Automated backups with short retention (3 days)
- VPC isolation with security groups
- Password stored in AWS Secrets Manager
- Optional automated start/stop scheduling
- Performance Insights (optional)

Architecture: Layer 4 template that CALLS other Layer 4 templates (VPC) 
and composes resources via factory.create() (Pattern B)
"""
import json
import random
import string
from typing import Any, Dict, Optional

import pulumi
import pulumi_aws as aws

from provisioner.templates.base import (
    InfrastructureTemplate,
    template_registry
)
from provisioner.templates.atomic_factory import PulumiAtomicFactory as factory
from provisioner.utils.aws import ResourceNamer, get_standard_tags
from provisioner.utils.aws.cidr_utils import generate_random_vpc_cidr
from provisioner.templates.templates.aws.database.rds_postgres_nonprod.config import RDSPostgresNonProdConfig
from provisioner.templates.templates.aws.networking.vpc_nonprod.pulumi import VPCSimpleNonprodTemplate


@template_registry("aws-rds-postgres-nonprod")
class RDSPostgresNonProdTemplate(InfrastructureTemplate):
    """
    RDS PostgreSQL Non-Production Template

    Creates a cost-optimized PostgreSQL database for nonprod environments:
    - VPC with public/private subnets (created by default, or use existing)
    - RDS PostgreSQL instance (db.t3.micro default)
    - Auto-scaling storage (20GB-100GB default)
    - DB subnet group (if VPC/subnets provided)
    - Security group with configurable access
    - Password stored in AWS Secrets Manager
    - Automated backups (3-day retention)
    - Optional Performance Insights
    """

    def __init__(self, name: str = None, config: Dict[str, Any] = None, **kwargs):
        """
        Initialize RDS PostgreSQL nonprod template
        """
        raw_config = config or kwargs or {}

        if name is None:
            name = raw_config.get('dbName', 'postgres-nonprod')

        super().__init__(name, raw_config)
        self.cfg = RDSPostgresNonProdConfig(raw_config)

        # Layer 4 sub-templates
        self.vpc_template: Optional[VPCSimpleNonprodTemplate] = None
        
        # Resources (Pattern B)
        self.db_instance = None
        self.db_subnet_group = None
        self.security_groups = []
        self.db_password_secret = None
        self.db_password_version = None
        self.postgres_ingress_rule = None

    def create_infrastructure(self) -> Dict[str, Any]:
        """Deploy infrastructure (implements abstract method)"""
        return self.create()

    def create(self) -> Dict[str, Any]:
        """Deploy RDS PostgreSQL infrastructure using factory pattern"""
        # Initialize ResourceNamer
        namer = ResourceNamer(
            project=self.cfg.project_name,
            environment=self.cfg.environment,
            region=self.cfg.region,
            template="aws-rds-postgres-nonprod"
        )
        
        # Generate names
        db_identifier = namer.rds(engine="postgres", identifier=self.cfg.db_name)
        
        # Generate standard tags
        tags = get_standard_tags(
            project=self.cfg.project_name,
            environment=self.cfg.environment,
            template="rds-postgres-nonprod"
        )
        tags.update(self.cfg.tags)

        print(f"[RDS-NONPROD] Creating PostgreSQL database for {self.cfg.environment}...")

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
                "az_1": f"{self.cfg.region}a"
            }
            
            self.vpc_template = VPCSimpleNonprodTemplate(
                name=f"{self.name}-vpc",
                config=vpc_config
            )
            self.vpc_template.create_infrastructure()
            vpc_outputs = self.vpc_template.get_outputs()
            
            vpc_id = vpc_outputs['vpc_id']
            # Pattern B compatibility: use flat key db_subnet_ids if available
            subnet_ids = vpc_outputs.get('db_subnet_ids', vpc_outputs.get('private_subnet_ids', []))
        else:
            vpc_id = self.cfg.vpc_id
            subnet_ids = self.cfg.subnet_ids

        # ========================================
        # STEP 2: GENERATE SECURE PASSWORD
        # ========================================
        chars = string.ascii_letters + string.digits + "!#$%&()*+,-.:;<=>?[]^_{|}~"
        db_password = ''.join(random.SystemRandom().choice(chars) for _ in range(32))

        # ========================================
        # STEP 3: SECURITY GROUPS
        # ========================================
        sg_id = None
        if self.cfg.vpc_mode == 'new' and self.vpc_template:
            vpc_outputs = self.vpc_template.get_outputs()
            # Try to get flattened key first
            sg_id = vpc_outputs.get('db_security_group_id')
        
        if not sg_id:
            # Create dedicated SG
            sg_name = namer.security_group(purpose="db", ports=[5432], service="postgres")
            fallback_sg = factory.create(
                "aws:ec2:SecurityGroup",
                sg_name,
                vpc_id=vpc_id,
                description=f"PostgreSQL access for {self.cfg.environment}",
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
        self.postgres_ingress_rule = aws.ec2.SecurityGroupRule(
            f"{self.name}-postgres-ingress",
            type="ingress",
            security_group_id=sg_id,
            protocol="tcp",
            from_port=5432,
            to_port=5432,
            cidr_blocks=self.cfg.allowed_cidr_blocks,
            description=f"PostgreSQL access for {db_identifier} ({self.cfg.environment})"
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
        self.db_password_secret = aws.secretsmanager.Secret(
            f"{self.name}-password",
            name=f"secret-db-{namer.project}-password-nonprod-{namer.region_short}",
            description=f"Master password for {db_identifier}",
            recovery_window_in_days=7,
            tags=tags
        )

        self.db_password_version = aws.secretsmanager.SecretVersion(
            f"{self.name}-password-version",
            secret_id=self.db_password_secret.id,
            secret_string=pulumi.Output.secret(db_password)
        )

        # ========================================
        # STEP 6: RDS INSTANCE
        # ========================================
        self.db_instance = factory.create(
            "aws:rds:Instance",
            db_identifier,
            engine="postgres",
            engine_version=self.cfg.engine_version,
            instance_class=self.cfg.db_instance_class,
            allocated_storage=self.cfg.allocated_storage,
            max_allocated_storage=self.cfg.max_allocated_storage,
            username=self.cfg.db_username,
            password=db_password,
            db_subnet_group_name=db_subnet_group_name,
            vpc_security_group_ids=[sg_id],
            db_name=self.cfg.db_name,
            storage_type="gp3",
            storage_encrypted=self.cfg.storage_encrypted,
            publicly_accessible=self.cfg.publicly_accessible,
            multi_az=self.cfg.multi_az,
            backup_retention_period=self.cfg.backup_retention_days,
            skip_final_snapshot=self.cfg.skip_final_snapshot,
            deletion_protection=self.cfg.deletion_protection_enabled,
            performance_insights_enabled=self.cfg.enable_performance_insights,
            tags={**tags, "Name": db_identifier}
        )

        # ========================================
        # STEP 7: EXPORT OUTPUTS
        # ========================================
        connection_string = pulumi.Output.concat(
            "postgresql://", self.cfg.db_username, "@", self.db_instance.address, ":",
            self.db_instance.port.apply(str), "/", self.cfg.db_name
        )

        pulumi.export("db_instance_id", self.db_instance.id)
        pulumi.export("db_address", self.db_instance.address)
        pulumi.export("db_port", self.db_instance.port)
        pulumi.export("db_endpoint", self.db_instance.endpoint)
        pulumi.export("connection_string", connection_string)
        pulumi.export("db_password_secret_name", self.db_password_secret.name)

        return self.get_outputs()

    def get_outputs(self) -> Dict[str, Any]:
        """Get template outputs (Pattern B)"""
        if not self.db_instance:
            return {"status": "not_created"}

        outputs = {
            "db_instance_id": self.db_instance.id,
            "db_address": self.db_instance.address,
            "db_port": self.db_instance.port,
            "db_name": self.cfg.db_name,
            "db_username": self.cfg.db_username,
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
    def get_config_schema(cls) -> Dict[str, Any]:
        return RDSPostgresNonProdConfig.get_config_schema()

    @classmethod
    def get_metadata(cls) -> Dict[str, Any]:
        """Pattern B Metadata source of truth"""
        return {
            "name": "aws-rds-postgres-nonprod",
            "title": "PostgreSQL Database",
            "description": "Cost-optimized managed PostgreSQL deployment for development and staging.",
            "category": "database",
            "version": "1.2.0",
            "author": "InnovativeApps",
            "cloud": "aws",
            "environment": "nonprod",
            "base_cost": "$20/month",
            "features": [
                "GP3 Storage with Auto-Scaling",
                "Secrets Manager Password Integration",
                "Automated Backups",
                "VPC Isolation",
                "Performance Insights"
            ],
            "tags": ["rds", "postgres", "database", "nonprod"],
            "deployment_time": "10-15 minutes",
            "complexity": "medium",
            "pillars": [
                {
                    "title": "Efficiency",
                    "score": "excellent",
                    "score_color": "#10b981",
                    "description": "GP3 and burstable instances minimize costs."
                }
            ]
        }
