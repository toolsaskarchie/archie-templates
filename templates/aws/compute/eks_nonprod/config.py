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
                # --- VPC Configuration (when vpc_mode=new) ---
                "use_custom_cidr": {
                    "type": "boolean",
                    "title": "Use Custom CIDR",
                    "description": "Specify a custom CIDR block instead of auto-generated",
                    "default": False,
                    "visibleIf": {"vpc_mode": "new"},
                    "group": "VPC Configuration",
                    "order": 50
                },
                "custom_cidr_block": {
                    "type": "string",
                    "title": "Custom CIDR Block",
                    "description": "Custom VPC CIDR block (e.g. 10.0.0.0/16)",
                    "placeholder": "10.0.0.0/16",
                    "visibleIf": {"use_custom_cidr": True, "vpc_mode": "new"},
                    "group": "VPC Configuration",
                    "order": 51
                },
                "enable_dns_support": {
                    "type": "boolean",
                    "title": "Enable DNS Support",
                    "description": "Enable DNS resolution within the VPC",
                    "default": True,
                    "visibleIf": {"vpc_mode": "new"},
                    "group": "VPC Configuration",
                    "order": 52
                },
                "enable_dns_hostnames": {
                    "type": "boolean",
                    "title": "Enable DNS Hostnames",
                    "description": "Enable DNS hostnames for instances in the VPC",
                    "default": True,
                    "visibleIf": {"vpc_mode": "new"},
                    "group": "VPC Configuration",
                    "order": 53
                },
                "ssh_access_ip": {
                    "type": "string",
                    "title": "SSH Access IP/CIDR",
                    "description": "IP address or CIDR block allowed for SSH access",
                    "placeholder": "203.0.113.0/32",
                    "visibleIf": {"vpc_mode": "new"},
                    "group": "VPC Configuration",
                    "order": 54
                },
                "enable_nat_gateway": {
                    "type": "boolean",
                    "title": "Enable NAT Gateway",
                    "description": "Enable NAT gateway for private subnet internet access",
                    "default": True,
                    "cost_impact": "$32/mo per gateway",
                    "visibleIf": {"vpc_mode": "new"},
                    "group": "VPC Configuration",
                    "order": 55
                },
                "enable_ssh_access": {
                    "type": "boolean",
                    "title": "Enable SSH Security Group",
                    "description": "Create a security group allowing SSH access",
                    "default": False,
                    "visibleIf": {"vpc_mode": "new"},
                    "group": "VPC Configuration",
                    "order": 56
                },
                "enable_flow_logs": {
                    "type": "boolean",
                    "title": "Enable VPC Flow Logs",
                    "description": "Enable VPC flow logs for network monitoring",
                    "default": True,
                    "visibleIf": {"vpc_mode": "new"},
                    "group": "VPC Configuration",
                    "order": 57
                },
                "flow_log_retention": {
                    "type": "number",
                    "title": "Flow Logs Retention (days)",
                    "description": "Number of days to retain VPC flow logs",
                    "default": 7,
                    "visibleIf": {"vpc_mode": "new"},
                    "group": "VPC Configuration",
                    "order": 58
                },
                "enable_rds_endpoint": {
                    "type": "boolean",
                    "title": "Enable RDS VPC Endpoint",
                    "description": "Create a VPC endpoint for RDS access",
                    "default": False,
                    "visibleIf": {"vpc_mode": "new"},
                    "group": "VPC Configuration",
                    "order": 59
                },
                "enable_ssm_endpoints": {
                    "type": "boolean",
                    "title": "Enable SSM VPC Endpoints",
                    "description": "Create VPC endpoints for AWS Systems Manager",
                    "default": True,
                    "cost_impact": "$22/mo",
                    "visibleIf": {"vpc_mode": "new"},
                    "group": "VPC Configuration",
                    "order": 60
                },
                "team_name": {
                    "type": "string",
                    "default": "",
                    "title": "Team Name",
                    "description": "Team that owns this resource",
                    "order": 70,
                    "group": "Tags",
                },
            },
            "required": ["project_name", "cluster_name"]
        }
