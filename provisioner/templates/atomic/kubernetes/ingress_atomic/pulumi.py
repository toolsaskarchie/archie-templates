"""Kubernetes Ingress Template"""
from typing import Dict, Any, Optional
import pulumi
import pulumi_kubernetes as kubernetes

from provisioner.templates.atomic.base import AtomicTemplate


class K8sIngressAtomicTemplate(AtomicTemplate):
    """Kubernetes Ingress Template
    
    Creates a Kubernetes Ingress.
    
    Creates:
        - kubernetes.networking.v1.Ingress
    
    Outputs:
        - ingress_name: Ingress name
    """
    
    def __init__(self, name: str, config: Dict[str, Any], **kwargs):
        """Initialize K8s Ingress atomic template"""
        super().__init__(name, config, **kwargs)
        self.ingress_name = config.get('ingress_name', name)
        self.namespace = config.get('namespace', 'default')
        self.ingress_class = config.get('ingress_class')
        self.annotations = config.get('annotations', {})
        self.rules = config.get('rules', [])
        self.tls = config.get('tls', [])
        self.labels = config.get('labels', {})
        self.provider = config.get('provider')
        self.depends_on = config.get('depends_on')
        self.ingress: Optional[kubernetes.networking.v1.Ingress] = None
    
    def create_infrastructure(self) -> Dict[str, Any]:
        """Create Kubernetes Ingress"""
        opts_args = {}
        if self.provider:
            opts_args['provider'] = self.provider
        if self.depends_on:
            opts_args['depends_on'] = self.depends_on
        
        opts = pulumi.ResourceOptions(**opts_args) if opts_args else self.resource_options
        
        self.ingress = kubernetes.networking.v1.Ingress(
            f"{self.name}-ingress",
            metadata=kubernetes.meta.v1.ObjectMetaArgs(
                name=self.ingress_name,
                namespace=self.namespace,
                annotations=self.annotations,
                labels=self.labels
            ),
            spec=kubernetes.networking.v1.IngressSpecArgs(
                ingress_class_name=self.ingress_class,
                rules=[
                    kubernetes.networking.v1.IngressRuleArgs(
                        host=rule.get('host'),
                        http=kubernetes.networking.v1.HTTPIngressRuleValueArgs(
                            paths=[
                                kubernetes.networking.v1.HTTPIngressPathArgs(
                                    path=path.get('path', '/'),
                                    path_type=path.get('path_type', 'Prefix'),
                                    backend=kubernetes.networking.v1.IngressBackendArgs(
                                        service=kubernetes.networking.v1.IngressServiceBackendArgs(
                                            name=path.get('backend', {}).get('service', {}).get('name'),
                                            port=kubernetes.networking.v1.ServiceBackendPortArgs(
                                                number=path.get('backend', {}).get('service', {}).get('port', {}).get('number')
                                            )
                                        )
                                    )
                                )
                                for path in rule.get('http', {}).get('paths', [])
                            ]
                        )
                    )
                    for rule in self.rules
                ] if self.rules else None,
                tls=self.tls if self.tls else None
            ),
            opts=opts
        )
        
        pulumi.export(f"{self.name}_ingress_name", self.ingress.metadata.name)
        
        return self.get_outputs()
    
    def get_outputs(self) -> Dict[str, Any]:
        """Get Ingress outputs"""
        if not self.ingress:
            raise RuntimeError(f"Ingress {self.name} not created")
        
        return {
            "ingress_name": self.ingress.metadata.name,
            "namespace": self.ingress.metadata.namespace,
        }
