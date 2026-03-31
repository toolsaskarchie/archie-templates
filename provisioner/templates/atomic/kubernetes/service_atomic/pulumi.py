"""Kubernetes Service Template"""
from typing import Dict, Any
import pulumi
import pulumi_kubernetes as kubernetes

from provisioner.templates.atomic.base import AtomicTemplate


class K8sServiceAtomicTemplate(AtomicTemplate):
    """Kubernetes Service Template
    
    Creates a Kubernetes Service.
    
    Creates:
        - kubernetes.core.v1.Service
    
    Outputs:
        - service_name: Service name
        - cluster_ip: Service cluster IP
    """
    
    def __init__(self, name: str, config: Dict[str, Any], **kwargs):
        """Initialize K8s Service atomic template"""
        super().__init__(name, config, **kwargs)
        self.service_name = config.get('service_name', name)
        self.namespace = config.get('namespace', 'default')
        self.service_type = config.get('service_type', 'ClusterIP')
        self.selector = config.get('selector', {})
        self.ports = config.get('ports', [])
        self.labels = config.get('labels', {})
        self.provider = config.get('provider')
        self.depends_on = config.get('depends_on')
        self.service: kubernetes.core.v1.Service = None
    
    def create_infrastructure(self) -> Dict[str, Any]:
        """Create Kubernetes Service"""
        opts_args = {}
        if self.provider:
            opts_args['provider'] = self.provider
        if self.depends_on:
            opts_args['depends_on'] = self.depends_on
        
        opts = pulumi.ResourceOptions(**opts_args) if opts_args else self.resource_options
        
        self.service = kubernetes.core.v1.Service(
            f"{self.name}-service",
            metadata=kubernetes.meta.v1.ObjectMetaArgs(
                name=self.service_name,
                namespace=self.namespace,
                labels=self.labels
            ),
            spec=kubernetes.core.v1.ServiceSpecArgs(
                type=self.service_type,
                selector=self.selector,
                ports=[
                    kubernetes.core.v1.ServicePortArgs(
                        port=p.get('port'),
                        target_port=p.get('target_port'),
                        protocol=p.get('protocol', 'TCP')
                    )
                    for p in self.ports
                ]
            ),
            opts=opts
        )
        
        pulumi.export(f"{self.name}_service_name", self.service.metadata.name)
        pulumi.export(f"{self.name}_namespace", self.service.metadata.namespace)
        pulumi.export(f"{self.name}_cluster_ip", self.service.spec.cluster_ip)

        return self.get_outputs()
    
    def get_outputs(self) -> Dict[str, Any]:
        """Get Service outputs"""
        if not self.service:
            raise RuntimeError(f"Service {self.name} not created")
        
        return {
            "service_name": self.service.metadata.name,
            "namespace": self.service.metadata.namespace,
            "cluster_ip": self.service.spec.cluster_ip if self.service.spec else None,
        }
