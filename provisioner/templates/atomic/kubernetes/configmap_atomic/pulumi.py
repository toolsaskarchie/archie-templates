"""Kubernetes ConfigMap Template"""
from typing import Dict, Any
import pulumi
import pulumi_kubernetes as kubernetes

from provisioner.templates.atomic.base import AtomicTemplate


class K8sConfigMapAtomicTemplate(AtomicTemplate):
    """Kubernetes ConfigMap Template
    
    Creates a Kubernetes ConfigMap.
    
    Creates:
        - kubernetes.core.v1.ConfigMap
    
    Outputs:
        - configmap_name: ConfigMap name
    """
    
    def __init__(self, name: str, config: Dict[str, Any], **kwargs):
        """Initialize K8s ConfigMap atomic template"""
        super().__init__(name, config, **kwargs)
        self.configmap_name = config.get('configmap_name', name)
        self.namespace = config.get('namespace', 'default')
        self.data = config.get('data', {})
        self.labels = config.get('labels', {})
        self.provider = config.get('provider')
        self.configmap: kubernetes.core.v1.ConfigMap = None
    
    def create_infrastructure(self) -> Dict[str, Any]:
        """Create Kubernetes ConfigMap"""
        opts = pulumi.ResourceOptions(provider=self.provider) if self.provider else self.resource_options
        
        self.configmap = kubernetes.core.v1.ConfigMap(
            f"{self.name}-configmap",
            metadata=kubernetes.meta.v1.ObjectMetaArgs(
                name=self.configmap_name,
                namespace=self.namespace,
                labels=self.labels
            ),
            data=self.data,
            opts=opts
        )
        
        pulumi.export(f"{self.name}_configmap_name", self.configmap.metadata.name)
        
        return self.get_outputs()
    
    def get_outputs(self) -> Dict[str, Any]:
        """Get ConfigMap outputs"""
        if not self.configmap:
            raise RuntimeError(f"ConfigMap {self.name} not created")
        
        return {
            "configmap_name": self.configmap.metadata.name,
            "namespace": self.configmap.metadata.namespace,
        }
