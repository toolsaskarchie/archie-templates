"""GCP Storage Bucket Template"""
from typing import Dict, Any, Optional
import pulumi
import pulumi_gcp as gcp

from provisioner.templates.atomic.base import AtomicTemplate
class GCPStorageBucketAtomicTemplate(AtomicTemplate):
    """GCP Storage Bucket Template
    
    Creates a Google Cloud Storage bucket.
    
    Creates:
        - gcp.storage.Bucket (direct GCP resource)
    
    Outputs:
        - bucket_name: Bucket name
        - bucket_url: Bucket URL
    """
    
    def __init__(self, name: str, config: Dict[str, Any], **kwargs):
        """Initialize GCP Storage Bucket atomic template"""
        super().__init__(name, config, **kwargs)
        self.bucket_name = config.get('bucket_name')
        self.location = config.get('location', 'US')
        self.project = config.get('project')
        self.labels = config.get('labels', {})
        self.website = config.get('website')
        self.uniform_bucket_level_access = config.get('uniform_bucket_level_access', True)
        self.bucket: Optional[gcp.storage.Bucket] = None
    
    def create_infrastructure(self) -> Dict[str, Any]:
        """Create GCP Storage bucket"""
        bucket_args = {
            "name": self.bucket_name,
            "location": self.location,
            "project": self.project,
            "labels": self.labels,
            "uniform_bucket_level_access": self.uniform_bucket_level_access,
        }
        
        if self.website:
            bucket_args["website"] = self.website
        
        # Create bucket directly (no ComponentResource wrapper)
        self.bucket = gcp.storage.Bucket(
            self.name,
            **bucket_args,
            opts=self.resource_options
        )
        
        pulumi.export(f"{self.name}_bucket_name", self.bucket.name)
        pulumi.export(f"{self.name}_bucket_url", self.bucket.url)
        
        return self.get_outputs()
    
    def get_outputs(self) -> Dict[str, Any]:
        """Get Storage bucket outputs"""
        if not self.bucket:
            raise RuntimeError(f"Storage bucket {self.name} not created")
        
        return {
            "bucket_name": self.bucket.name,
            "bucket_url": self.bucket.url,
            "bucket_id": self.bucket.id,
        }
