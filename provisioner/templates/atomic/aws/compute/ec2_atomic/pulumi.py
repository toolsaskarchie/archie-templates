"""
EC2 Template
Creates a single EC2 instance resource - this is a true atomic resource.

Architecture: Layer 3 atomic that wraps Layer 2 component
"""
from typing import Any, Dict, Optional
import pulumi
import pulumi_aws as aws

from provisioner.templates.base import (
    InfrastructureTemplate,
    template_registry
)
from provisioner.utils.aws import get_standard_tags
from provisioner.templates.atomic.aws.compute.ec2_atomic.config import EC2AtomicConfig


@template_registry("aws-ec2-atomic")
class EC2AtomicTemplate(InfrastructureTemplate):
    """
    EC2 Template
    
    Creates only an EC2 instance resource with:
    - Configurable AMI, instance type, and subnet
    - Security group associations
    - Optional IAM instance profile
    - Optional key pair for SSH access
    - Optional user data script
    
    This is a Layer 3 atomic - requires VPC, subnet, and security groups to exist.
    """
    
    def __init__(self, name: str = None, config: Dict[str, Any] = None, **kwargs):
        """Initialize template"""
        raw_config = config or kwargs or {}
        
        if name is None:
            name = raw_config.get('parameters', {}).get('aws', {}).get('instance_name', 'ec2-instance')
        
        super().__init__(name, raw_config)
        self.cfg = EC2AtomicConfig(raw_config)
        
        # Resources
        self.ec2_instance: Optional[aws.ec2.Instance] = None
    
    def create_infrastructure(self) -> Dict[str, Any]:
        """Create EC2 instance directly - shows as actual AWS resource in preview (Layer 2)"""
        tags = get_standard_tags(
            project=self.cfg.project_name,
            environment=self.cfg.environment,
            template="ec2-atomic"
        )
        
        # Strip description text from parameters if present
        instance_name = self.cfg.instance_name
        instance_name = instance_name.split('(')[0].strip() if isinstance(instance_name, str) and '(' in instance_name else instance_name
        
        ami_id = self.cfg.ami_id
        ami_id = ami_id.split('(')[0].strip() if isinstance(ami_id, str) and '(' in ami_id else ami_id
        
        instance_type = self.cfg.instance_type
        instance_type = instance_type.split('(')[0].strip() if isinstance(instance_type, str) and '(' in instance_type else instance_type
        
        # Resolve AMI from SSM parameter if needed
        if ami_id.startswith('resolve-ssm:'):
            ami = aws.ec2.get_ami(
                most_recent=True,
                owners=["amazon"],
                filters=[
                    aws.ec2.GetAmiFilterArgs(
            "name",
                        values=["amzn2-ami-hvm-*-x86_64-gp2"]
                    ),
                    aws.ec2.GetAmiFilterArgs(
            "state",
                        values=["available"]
                    )
                ]
            )
            ami_id = ami.id
        
        # Create EC2 instance using component (Layer 2)
        print(f"[EC2] Creating EC2 instance '{instance_name}'")
        # Use pattern: aws.ec2.Instance(f"{self.name}-instance", ...)
        self.ec2_instance = aws.ec2.Instance(
            self.name,
            subnet_id=self.cfg.subnet_id,
            ami=ami_id,
            instance_type=instance_type,
            vpc_security_group_ids=self.cfg.security_group_ids,
            iam_instance_profile=self.cfg.iam_instance_profile,
            key_name=self.cfg.key_name,
            user_data=self.cfg.user_data,
            tags={**tags, "Name": instance_name}
        )
        
        # Export outputs
        pulumi.export("instance_id", self.ec2_instance.id)
        pulumi.export("instance_name", instance_name)
        pulumi.export("private_ip", self.ec2_instance.private_ip)
        pulumi.export("public_ip", self.ec2_instance.public_ip)
        pulumi.export("instance_type", instance_type)
        pulumi.export("ami_id", ami_id)
        
        print(f"[EC2] Instance created successfully")
        
        return {
            "template_name": "ec2-atomic",
            "outputs": {
                "instance_id": "Available after deployment",
                "instance_name": instance_name,
                "instance_type": instance_type
            }
        }
    
    def get_outputs(self) -> Dict[str, Any]:
        """Get template outputs"""
        if not self.ec2_instance:
            return {
                "instance_name": self.cfg.instance_name,
                "instance_type": self.cfg.instance_type,
                "status": "not_created"
            }
        
        outputs = {
            "instance_id": self.ec2_instance.id,
            "instance_name": self.cfg.instance_name,
            "instance_type": self.cfg.instance_type,
            "private_ip": self.ec2_instance.private_ip,
            "ami_id": self.cfg.ami_id,
            "subnet_id": self.cfg.subnet_id
        }
        
        # Add public IP if instance has one
        if self.ec2_instance.public_ip:
            outputs["public_ip"] = self.ec2_instance.public_ip
        
        return outputs
    
    @classmethod
    def get_metadata(cls) -> Dict[str, Any]:
        """Template metadata"""
        return {
            "name": "ec2-atomic",
            "title": "EC2 Instance",
            "subtitle": "Single EC2 instance resource",
            "description": "Create a standalone EC2 instance with configurable AMI, instance type, security groups, and user data. This is an atomic resource containing only the EC2 instance itself - requires existing VPC, subnet, and security groups.",
            "category": "compute",
            "provider": "aws",
            "tier": "atomic",
            "complexity": "simple",
            "icon": "💻",
            "version": "1.0.0",
            "status": "stable",
            "estimated_cost": "$7-30/month (depends on instance type)",
            "deployment_time": "1-2 minutes",
            "use_cases": [
                "Add instance to existing infrastructure",
                "Expert users building custom architectures",
                "Testing and learning EC2 concepts"
            ],
            "features": [
                "Single EC2 instance resource",
                "Configurable AMI and instance type",
                "Security group associations",
                "IAM instance profile support",
                "SSH key pair support",
                "User data scripts"
            ],
            "outputs": [
                "Instance ID",
                "Instance name",
                "Private IP address",
                "Public IP address (if applicable)",
                "Instance type",
                "AMI ID"
            ],
            "prerequisites": [
                "VPC must exist",
                "Subnet must exist",
                "Security groups must exist"
            ],
            "tags": [
                "ec2",
                "compute",
                "atomic",
                "instance"
            ]
        }
    
    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        """JSON Schema for configuration"""
        return {
            "type": "object",
            "title": "EC2",
            "properties": {
                "instanceName": {
                    "type": "string",
                    "title": "Instance Name",
                    "description": "Name for the EC2 instance",
                    "default": "my-ec2-instance"
                },
                "amiId": {
                    "type": "string",
                    "title": "AMI ID",
                    "description": "Amazon Machine Image ID (e.g., ami-xxxxx)",
                    "pattern": "^ami-[a-zA-Z0-9]+$"
                },
                "instanceType": {
                    "type": "string",
                    "title": "Instance Type",
                    "description": "EC2 instance type",
                    "enum": ["t3.micro", "t3.small", "t3.medium", "t3.large"],
                    "default": "t3.micro"
                },
                "subnetId": {
                    "type": "string",
                    "title": "Subnet ID",
                    "description": "Subnet where instance will be launched",
                    "pattern": "^subnet-[a-zA-Z0-9]+$"
                },
                "securityGroupIds": {
                    "type": "array",
                    "title": "Security Group IDs",
                    "description": "List of security groups for the instance",
                    "items": {
                        "type": "string",
                        "pattern": "^sg-[a-zA-Z0-9]+$"
                    },
                    "minItems": 1
                },
                "keyName": {
                    "type": "string",
                    "title": "SSH Key Pair Name",
                    "description": "Key pair name for SSH access (optional)"
                },
                "iamInstanceProfile": {
                    "type": "string",
                    "title": "IAM Instance Profile",
                    "description": "IAM instance profile name (optional)"
                },
                "userData": {
                    "type": "string",
                    "title": "User Data Script",
                    "description": "Bash script to run on instance launch (optional)"
                },
                "projectName": {
                    "type": "string",
                    "title": "Project Name",
                    "description": "Project name for tagging",
                    "default": "my-project"
                },
                "environment": {
                    "type": "string",
                    "title": "Environment",
                    "enum": ["dev", "test", "staging", "prod"],
                    "default": "dev"
                },
                "region": {
                    "type": "string",
                    "title": "AWS Region",
                    "description": "AWS region for deployment",
                    "default": "us-east-1"
                }
            },
            "required": ["instanceName", "amiId", "instanceType", "subnetId", "securityGroupIds"],
            "additionalProperties": False
        }
