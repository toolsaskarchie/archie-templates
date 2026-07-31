# Bootstrap a self-contained kubeconfig so the EKS deploy OUTPUT carries a
# credential Archie can register as a Kubernetes cloud account (no AWS-exec
# dependency). A cluster-admin ServiceAccount + a long-lived token Secret.
resource "kubernetes_service_account_v1" "deployer" {
  metadata {
    name      = "archie-deployer"
    namespace = "kube-system"
  }
  depends_on = [module.eks]
}

resource "kubernetes_cluster_role_binding_v1" "deployer" {
  metadata {
    name = "archie-deployer"
  }
  role_ref {
    api_group = "rbac.authorization.k8s.io"
    kind      = "ClusterRole"
    name      = "cluster-admin"
  }
  subject {
    kind      = "ServiceAccount"
    name      = kubernetes_service_account_v1.deployer.metadata[0].name
    namespace = "kube-system"
  }
}

resource "kubernetes_secret_v1" "deployer_token" {
  metadata {
    name      = "archie-deployer-token"
    namespace = "kube-system"
    annotations = {
      "kubernetes.io/service-account.name" = kubernetes_service_account_v1.deployer.metadata[0].name
    }
  }
  type                           = "kubernetes.io/service-account-token"
  wait_for_service_account_token = true
}

locals {
  kubeconfig = yamlencode({
    apiVersion        = "v1"
    kind              = "Config"
    "current-context" = "archie"
    clusters = [{
      name = "archie"
      cluster = {
        server                        = module.eks.cluster_endpoint
        "certificate-authority-data"  = module.eks.cluster_certificate_authority_data
      }
    }]
    users = [{
      name = "archie-deployer"
      user = {
        token = kubernetes_secret_v1.deployer_token.data["token"]
      }
    }]
    contexts = [{
      name = "archie"
      context = {
        cluster = "archie"
        user    = "archie-deployer"
      }
    }]
  })
}
