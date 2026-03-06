"""
Configuration parser for EKS Non-Prod Template
"""
from typing import Dict, Any, Optional, List

class EKSNonProdConfig:
    """Parsed and validated configuration for EKS Non-Prod Template"""
    
    def __init__(self, template_or_config: Any):
        """Parse configuration from user input or template instance"""
        if hasattr(template_or_config, 'get_parameter'):
            self.template = template_or_config
            self.raw_config = self.template.config
        else:
            self.template = None
            self.raw_config = template_or_config

        self.parameters = self.raw_config.get('parameters', {}).get('aws', {}) or self.raw_config.get('parameters', {})
        
        # Meta attributes
        self.environment = self.raw_config.get('environment', 'nonprod')
        self.region = self.raw_config.get('region', 'us-east-1')
        self.tags = self.raw_config.get('tags', {})

        # Cluster Settings
        self.cluster_name = self.get_parameter('cluster_name', self.get_parameter('clusterName', 'eks-nonprod'))
        self.kubernetes_version = self.get_parameter('kubernetes_version', self.get_parameter('kubernetesVersion', '1.28'))
        
        # Node Settings
        self.node_mode = self.get_parameter('node_mode', self.get_parameter('nodeMode', 'managed'))
        self.node_instance_type = self.get_parameter('node_instance_type', self.get_parameter('nodeInstanceType', 't3.small'))
        self.desired_capacity = int(self.get_parameter('desired_capacity', self.get_parameter('desiredCapacity', 1)))
        self.min_size = int(self.get_parameter('min_size', self.get_parameter('minSize', 1)))
        self.max_size = int(self.get_parameter('max_size', self.get_parameter('maxSize', 2)))
        
        # Networking & Connectivity
        self.vpc_mode = self.get_parameter('vpc_mode', self.get_parameter('vpcMode', 'new'))
        self.vpc_id = self.get_parameter('vpc_id', self.get_parameter('vpcId'))
        self.vpc_cidr = self.get_parameter('vpc_cidr', self.get_parameter('vpcCidr', '10.0.0.0/16'))
        self.private_subnet_ids = self.get_parameter('private_subnet_ids', self.get_parameter('privateSubnetIds', []))
        
        self.ssh_access_ip = self.get_parameter('ssh_access_ip', self.get_parameter('sshAccessIp'))
        if self.ssh_access_ip and '/' not in self.ssh_access_ip:
            self.ssh_access_ip = f"{self.ssh_access_ip}/32"

        # Optional Features
        self.deploy_nginx = self.get_parameter('deploy_nginx', self.get_parameter('deployNginx', True))

    def get_parameter(self, key: str, default: Any = None) -> Any:
        """Get a parameter from the configuration."""
        if self.template:
            return self.template.get_parameter(key, default)
        return self.parameters.get(key, default)

    @property
    def project_name(self) -> str:
        """Get project name from config."""
        return (
            self.get_parameter('projectName') or
            self.get_parameter('project_name') or
            self.raw_config.get('projectName') or
            self.raw_config.get('project_name') or
            'archie-eks-nonprod'
        )

    @staticmethod
    def get_config_schema() -> Dict[str, Any]:
        """Get JSON schema for UI configuration."""
        from provisioner.templates.templates.aws.networking.vpc_nonprod.pulumi import VPCSimpleNonprodTemplate
        from provisioner.templates.templates.aws.compute.ec2_nonprod.config import EC2NonProdConfig
        
        # Pull base schemas
        vpc_schema = VPCSimpleNonprodTemplate.get_config_schema()
        ec2_schema = EC2NonProdConfig.get_config_schema()
        
        # Merge logic: EKS specific fields + VPC base + EC2 base
        properties = {
            # Shared essentials from VPC
            **vpc_schema.get("properties", {}),
            # Merge EC2 compute/security fields
            **ec2_schema.get("properties", {}),
        }
        
        # EKS Specific additions
        properties.update({
            "eks_header": {
                "type": "separator",
                "title": "EKS Cluster Settings",
                "group": "Compute Selection",
                "isEssential": True,
                "order": 65
            },
            "cluster_name": {
                "type": "string",
                "title": "Cluster Name",
                "description": "Unique name for the EKS cluster",
                "placeholder": "eks-nonprod",
                "group": "Compute Selection",
                "isEssential": True,
                "order": 66
            },
            "kubernetes_version": {
                "type": "string",
                "title": "K8s Version",
                "description": "Kubernetes control plane version",
                "default": "1.28",
                "enum": ["1.27", "1.28", "1.29"],
                "group": "Compute Selection",
                "order": 67
            }
        })
        
        return {
            "type": "object",
            "properties": properties,
            "required": list(set(vpc_schema.get("required", []) + ec2_schema.get("required", []) + ["cluster_name"]))
        }
