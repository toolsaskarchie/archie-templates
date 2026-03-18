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
        return {
            "type": "object",
            "properties": {
                # --- Essentials ---
                "project_name": {
                    "type": "string",
                    "title": "Project Name",
                    "description": "Unique name for this project (used in resource naming)",
                    "group": "Essentials",
                    "isEssential": True,
                    "order": 1
                },
                "region": {
                    "type": "string",
                    "title": "AWS Region",
                    "description": "AWS region to deploy into",
                    "default": "us-east-1",
                    "enum": ["us-east-1", "us-east-2", "us-west-1", "us-west-2", "eu-west-1", "eu-central-1", "ap-southeast-1"],
                    "group": "Essentials",
                    "isEssential": True,
                    "order": 2
                },
                # --- Cluster ---
                "cluster_name": {
                    "type": "string",
                    "title": "Cluster Name",
                    "description": "Unique name for the EKS cluster",
                    "placeholder": "eks-nonprod",
                    "group": "Cluster",
                    "isEssential": True,
                    "order": 10
                },
                "kubernetes_version": {
                    "type": "string",
                    "title": "Kubernetes Version",
                    "description": "Kubernetes control plane version",
                    "default": "1.28",
                    "enum": ["1.27", "1.28", "1.29", "1.30"],
                    "group": "Cluster",
                    "isEssential": True,
                    "order": 11
                },
                # --- Nodes ---
                "node_instance_type": {
                    "type": "string",
                    "title": "Node Instance Type",
                    "description": "EC2 instance type for worker nodes",
                    "default": "t3.medium",
                    "enum": ["t3.small", "t3.medium", "t3.large", "t3.xlarge", "m5.large", "m5.xlarge"],
                    "group": "Nodes",
                    "isEssential": True,
                    "order": 20
                },
                "min_nodes": {
                    "type": "number",
                    "title": "Min Nodes",
                    "description": "Minimum number of worker nodes",
                    "default": 1,
                    "minimum": 1,
                    "maximum": 10,
                    "group": "Nodes",
                    "order": 21
                },
                "max_nodes": {
                    "type": "number",
                    "title": "Max Nodes",
                    "description": "Maximum number of worker nodes (for autoscaling)",
                    "default": 3,
                    "minimum": 1,
                    "maximum": 20,
                    "group": "Nodes",
                    "order": 22
                },
                "desired_nodes": {
                    "type": "number",
                    "title": "Desired Nodes",
                    "description": "Initial number of worker nodes",
                    "default": 2,
                    "minimum": 1,
                    "maximum": 10,
                    "group": "Nodes",
                    "order": 23
                },
                # --- Networking ---
                "vpc_mode": {
                    "type": "string",
                    "title": "VPC Mode",
                    "description": "Create a new VPC or use an existing one",
                    "default": "new",
                    "enum": ["new", "existing"],
                    "group": "Networking",
                    "isEssential": True,
                    "order": 30
                },
                "vpc_id": {
                    "type": "string",
                    "title": "Existing VPC ID",
                    "description": "ID of an existing VPC to deploy into",
                    "placeholder": "vpc-0abc123def456",
                    "visibleIf": {"vpc_mode": "existing"},
                    "group": "Networking",
                    "order": 31
                },
            },
            "required": ["project_name", "cluster_name"]
        }
