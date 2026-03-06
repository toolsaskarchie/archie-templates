"""Kubernetes Deployment Template"""
from typing import Dict, Any
import pulumi
import pulumi_kubernetes as kubernetes

from provisioner.templates.atomic.base import AtomicTemplate


class K8sDeploymentAtomicTemplate(AtomicTemplate):
    """Kubernetes Deployment Template
    
    Creates a Kubernetes Deployment.
    
    Creates:
        - kubernetes.apps.v1.Deployment
    
    Outputs:
        - deployment_name: Deployment name
    """
    
    def __init__(self, name: str, config: Dict[str, Any], **kwargs):
        """Initialize K8s Deployment atomic template"""
        super().__init__(name, config, **kwargs)
        self.deployment_name = config.get('deployment_name', name)
        self.namespace = config.get('namespace', 'default')
        self.metadata = config.get('metadata', {})
        self.spec = config.get('spec', {})
        self.provider = config.get('provider')
        self.depends_on = config.get('depends_on')
        self.deployment: kubernetes.apps.v1.Deployment = None
    
    def create_infrastructure(self) -> Dict[str, Any]:
        """Create Kubernetes Deployment"""
        opts_args = {}
        if self.provider:
            opts_args['provider'] = self.provider
        if self.depends_on:
            opts_args['depends_on'] = self.depends_on
        
        opts = pulumi.ResourceOptions(**opts_args) if opts_args else self.resource_options
        
        self.deployment = kubernetes.apps.v1.Deployment(
            f"{self.name}-deployment",
            metadata=kubernetes.meta.v1.ObjectMetaArgs(
                name=self.metadata.get('name', self.deployment_name),
                namespace=self.metadata.get('namespace', self.namespace),
                labels=self.metadata.get('labels', {})
            ),
            spec=kubernetes.apps.v1.DeploymentSpecArgs(
                replicas=self.spec.get('replicas', 1),
                selector=kubernetes.meta.v1.LabelSelectorArgs(
                    match_labels=self.spec.get('selector', {}).get('match_labels', {})
                ),
                template=kubernetes.core.v1.PodTemplateSpecArgs(
                    metadata=kubernetes.meta.v1.ObjectMetaArgs(
                        labels=self.spec.get('template', {}).get('metadata', {}).get('labels', {})
                    ),
                    spec=kubernetes.core.v1.PodSpecArgs(
                        containers=[
                            kubernetes.core.v1.ContainerArgs(
                                name=container.get('name'),
                                image=container.get('image'),
                                ports=[
                                    kubernetes.core.v1.ContainerPortArgs(container_port=p.get('container_port'))
                                    for p in container.get('ports', [])
                                ],
                                resources=kubernetes.core.v1.ResourceRequirementsArgs(
                                    requests=container.get('resources', {}).get('requests', {}),
                                    limits=container.get('resources', {}).get('limits', {})
                                ) if container.get('resources') else None,
                                env_from=[
                                    kubernetes.core.v1.EnvFromSourceArgs(
                                        config_map_ref=kubernetes.core.v1.ConfigMapEnvSourceArgs(
                                            name=env_from.get('config_map_ref', {}).get('name')
                                        )
                                    )
                                    for env_from in container.get('env_from', [])
                                ] if container.get('env_from') else None
                            )
                            for container in self.spec.get('template', {}).get('spec', {}).get('containers', [])
                        ]
                    )
                )
            ),
            opts=opts
        )
        
        pulumi.export(f"{self.name}_deployment_name", self.deployment.metadata.name)
        
        return self.get_outputs()
    
    def get_outputs(self) -> Dict[str, Any]:
        """Get Deployment outputs"""
        if not self.deployment:
            raise RuntimeError(f"Deployment {self.name} not created")
        
        return {
            "deployment_name": self.deployment.metadata.name,
            "namespace": self.deployment.metadata.namespace,
        }
