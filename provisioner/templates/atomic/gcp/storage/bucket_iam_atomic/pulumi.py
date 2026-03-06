"""GCP Bucket IAM Binding Template"""
from typing import Dict, Any, List, Optional
import pulumi
import pulumi_gcp as gcp

from provisioner.templates.atomic.base import AtomicTemplate
class GCPBucketIAMBindingAtomicTemplate(AtomicTemplate):
    """GCP Bucket IAM Binding Template
    
    Creates IAM policy binding for a GCP Storage bucket.
    
    Creates:
        - BucketIAMBindingComponent (wraps gcp.storage.BucketIAMBinding)
    
    Outputs:
        - bucket: Bucket name
        - role: IAM role
    """
    
    def __init__(self, name: str, config: Dict[str, Any], **kwargs):
        """Initialize GCP Bucket IAM Binding atomic template"""
        super().__init__(name, config, **kwargs)
        self.bucket = config.get('bucket')
        self.role = config.get('role')
        self.members = config.get('members', [])
        self.depends_on = config.get('depends_on')
        self.iam_binding: Optional[gcp.storage.BucketIAMBinding] = None
    
    def create_infrastructure(self) -> Dict[str, Any]:
        """Create GCP Bucket IAM binding"""
        opts_args = {}
        if self.depends_on:
            opts_args['depends_on'] = self.depends_on
        
        opts = pulumi.ResourceOptions(**opts_args) if opts_args else self.resource_options
        
        self.iam_binding = gcp.storage.BucketIAMBinding(
            name=self.name,
            bucket=self.bucket,
            role=self.role,
            members=self.members,
            opts=opts
        )
        
        pulumi.export(f"{self.name}_bucket", self.iam_binding.iam_binding.bucket)
        pulumi.export(f"{self.name}_role", self.iam_binding.iam_binding.role)
        
        return self.get_outputs()
    
    def get_outputs(self) -> Dict[str, Any]:
        """Get IAM binding outputs"""
        if not self.iam_binding:
            raise RuntimeError(f"IAM binding {self.name} not created")
        
        return {
            "bucket": self.iam_binding.iam_binding.bucket,
            "role": self.iam_binding.iam_binding.role,
        }
