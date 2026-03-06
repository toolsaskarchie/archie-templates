"""AWS Flow Logs Atomic Configuration"""
from dataclasses import dataclass
from typing import Any, Dict, Optional

@dataclass
class FlowLogsAtomicConfig:
    vpc_id: str
    project_name: str
    environment: str
    traffic_type: str = "ALL"
    destination_type: str = "cloud-watch-logs"
    log_group_name: Optional[str] = None
    retention_days: int = 7
    
    def __init__(self, config: Dict[str, Any]):
        aws_params = config.get('parameters', {}).get('aws', {})
        self.vpc_id = aws_params.get('vpc_id')
        self.traffic_type = aws_params.get('traffic_type', 'ALL')
        self.destination_type = aws_params.get('destination_type', 'cloud-watch-logs')
        self.project_name = aws_params.get('project_name', 'my-project')
        self.environment = aws_params.get('environment', 'dev')
        self.log_group_name = aws_params.get('log_group_name', f"/aws/vpc/{self.project_name}-{self.environment}")
        self.retention_days = int(aws_params.get('retention_days', aws_params.get('flow_log_retention', 7)))
        
        if not self.vpc_id:
            raise ValueError("vpc_id is required")
