"""
AWS Flow Logs Template
Creates a standalone AWS VPC Flow Logs using the VPCFlowLogsComponent.
"""
from typing import Any, Dict, Optional
import json
import pulumi
import pulumi_aws as aws

from provisioner.templates.base import template_registry, InfrastructureTemplate
from .config import FlowLogsAtomicConfig
from provisioner.utils.aws import get_standard_tags

@template_registry("aws-flow-logs-atomic")
class FlowLogsAtomicTemplate(InfrastructureTemplate):
    """
    AWS Flow Logs Template
    """
    
    def __init__(self, name: str = None, config: Dict[str, Any] = None, **kwargs):
        raw_config = config or kwargs or {}
        self.cfg = FlowLogsAtomicConfig(raw_config)
        
        if name is None:
            name = f"{self.cfg.project_name}-{self.cfg.environment}-flow-logs"
            
        super().__init__(name, raw_config)
        self.flow_logs: Optional[aws.ec2.FlowLog] = None

    def create_infrastructure(self) -> Dict[str, Any]:
        """Create Flow Logs directly - shows as actual AWS resource in preview"""
        tags = get_standard_tags(
            project=self.cfg.project_name,
            environment=self.cfg.environment,
            template="flow-logs-atomic"
        )
        
        # Create CloudWatch Log Group for flow logs
        self.log_group = aws.cloudwatch.LogGroup(
            f"{self.name}-log-group",
            name=self.cfg.log_group_name,
            retention_in_days=self.cfg.retention_days,
            tags=tags
        )
        
        # Create IAM role for Flow Logs if not provided
        iam_role_arn = None
        if hasattr(self.cfg, 'iam_role_arn') and self.cfg.iam_role_arn:
            iam_role_arn = self.cfg.iam_role_arn
        else:
            # Create IAM role for Flow Logs
            assume_role_policy = json.dumps({
                "Version": "2012-10-17",
                "Statement": [{
                    "Effect": "Allow",
                    "Principal": {"Service": "vpc-flow-logs.amazonaws.com"},
                    "Action": "sts:AssumeRole"
                }]
            })
            
            # Generate a short, unique name for the IAM role to stay within AWS 64-char limit
            import hashlib
            name_hash = hashlib.md5(self.name.encode()).hexdigest()[:8]
            short_role_name = f"fl-{name_hash}"
            
            flow_logs_role = aws.iam.Role(
                f"{self.name}-role",
                name=short_role_name,
                assume_role_policy=assume_role_policy,
                tags=tags
            )
            
            # Attach policy to allow writing to CloudWatch
            flow_logs_policy = aws.iam.RolePolicy(
                f"{self.name}-policy",
                role=flow_logs_role.id,
                policy=json.dumps({
                    "Version": "2012-10-17",
                    "Statement": [{
                        "Effect": "Allow",
                        "Action": [
                            "logs:CreateLogGroup",
                            "logs:CreateLogStream",
                            "logs:PutLogEvents",
                            "logs:DescribeLogGroups",
                            "logs:DescribeLogStreams"
                        ],
                        "Resource": "*"
                    }]
                })
            )
            
            iam_role_arn = flow_logs_role.arn
        
        # Create Flow Logs
        self.flow_logs = aws.ec2.FlowLog(
            self.name,
            vpc_id=self.cfg.vpc_id,
            traffic_type=self.cfg.traffic_type,
            log_destination_type="cloud-watch-logs",
            log_destination=self.log_group.arn,
            iam_role_arn=iam_role_arn,
            tags={**tags, "Name": self.name}
        )
        
        pulumi.export("flow_log_id", self.flow_logs.id)
        pulumi.export("log_group_name", self.log_group.name)
        
        return self.get_outputs()

    def get_outputs(self) -> Dict[str, Any]:
        if not self.flow_logs:
            return {}
        return {
            "flow_log_id": self.flow_logs.id,
            "log_group_name": self.log_group.name if hasattr(self, 'log_group') else None
        }

    @classmethod
    def get_metadata(cls):
        return {
            "name": "flow-logs-atomic",
            "title": "VPC Flow Logs",
            "description": "Standalone AWS VPC Flow Logs resource.",
            "category": "networking",
            "provider": "aws",
            "tier": "atomic"
        }
