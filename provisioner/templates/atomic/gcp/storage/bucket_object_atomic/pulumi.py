"""GCP Bucket Object Template"""
from typing import Dict, Any, Optional
import pulumi
import pulumi_gcp as gcp

from provisioner.templates.atomic.base import AtomicTemplate
class GCPBucketObjectAtomicTemplate(AtomicTemplate):
    """GCP Bucket Object Template
    
    Creates an object in a GCP Storage bucket.
    
    Creates:
        - BucketObjectComponent (wraps gcp.storage.BucketObject)
    
    Outputs:
        - object_name: Object name
        - media_link: Object media link
    """
    
    def __init__(self, name: str, config: Dict[str, Any], **kwargs):
        """Initialize GCP Bucket Object atomic template"""
        super().__init__(name, config, **kwargs)
        self.bucket = config.get('bucket')
        self.object_name = config.get('object_name')
        self.content = config.get('content')
        self.source = config.get('source')
        self.content_type = config.get('content_type')
        self.depends_on = config.get('depends_on')
        self.bucket_object: Optional[gcp.storage.BucketObject] = None
    
    def create_infrastructure(self) -> Dict[str, Any]:
        """Create GCP Bucket object"""
        opts_args = {}
        if self.depends_on:
            opts_args['depends_on'] = self.depends_on
        
        opts = pulumi.ResourceOptions(**opts_args) if opts_args else self.resource_options
        
        object_args = {
            "name": self.name,
            "bucket": self.bucket,
            "object_name": self.object_name,
        }
        
        if self.content:
            object_args["content"] = self.content
        
        if self.source:
            object_args["source"] = self.source
        
        if self.content_type:
            object_args["content_type"] = self.content_type
        
        self.bucket_object = gcp.storage.BucketObject(
            **object_args,
            opts=opts
        )
        
        pulumi.export(f"{self.name}_object_name", self.bucket_object.object.name)
        
        return self.get_outputs()
    
    def get_outputs(self) -> Dict[str, Any]:
        """Get Bucket object outputs"""
        if not self.bucket_object:
            raise RuntimeError(f"Bucket object {self.name} not created")
        
        return {
            "object_name": self.bucket_object.object.name,
            "media_link": self.bucket_object.object.media_link,
        }
