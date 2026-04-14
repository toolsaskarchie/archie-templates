"""Kubernetes Templates"""
from provisioner.templates.templates.kubernetes.web_app import K8sSimpleWebAppTemplate
from provisioner.templates.templates.kubernetes.helm_release import K8sHelmReleaseTemplate
from provisioner.templates.templates.kubernetes.statefulset import K8sStatefulSetTemplate
from provisioner.templates.templates.kubernetes.cronjob import K8sCronJobTemplate
from provisioner.templates.templates.kubernetes.namespace_setup import K8sNamespaceSetupTemplate
from provisioner.templates.templates.kubernetes.hpa import K8sHPATemplate
from provisioner.templates.templates.kubernetes.pvc import K8sPVCTemplate

__all__ = [
    "K8sSimpleWebAppTemplate",
    "K8sHelmReleaseTemplate",
    "K8sStatefulSetTemplate",
    "K8sCronJobTemplate",
    "K8sNamespaceSetupTemplate",
    "K8sHPATemplate",
    "K8sPVCTemplate",
]
