# A SELF-CONTAINED KUBECONFIG, published as an output.
#
# This is how Archie finds a cluster. When a Kubernetes workload is deployed, the
# worker looks for a managed cluster stack that publishes a `kubeconfig` OUTPUT
# and hands it to the workload's provider — see
# native_tf_engine._resolve_cluster_kubeconfig_output, which filters on
# Attr("outputs.kubeconfig").exists().
#
# Without it the workload has no reachable target and refuses to apply rather
# than defaulting to http://localhost. That is exactly what happened: this module
# published cluster_name, cluster_endpoint and cluster_ca — everything a human
# needs and nothing the platform looks for — so a cluster that was up and healthy
# was invisible to the very workload that had just been ordered onto it.
#
# Embedded-token rather than an `aws eks get-token` exec block on purpose: the
# consumer is a Terraform run in Archie's worker, which has no AWS CLI and no
# reason to hold this account's credentials just to reach a cluster it was handed.
resource "kubernetes_service_account_v1" "deployer" {
  metadata {
    name      = "archie-deployer"
    namespace = "kube-system"
  }
  depends_on = [aws_eks_node_group.main]
}

resource "kubernetes_cluster_role_binding_v1" "deployer" {
  metadata { name = "archie-deployer" }
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
        server                       = aws_eks_cluster.main.endpoint
        "certificate-authority-data" = aws_eks_cluster.main.certificate_authority[0].data
      }
    }]
    users = [{
      name = "archie-deployer"
      user = { token = kubernetes_secret_v1.deployer_token.data["token"] }
    }]
    contexts = [{
      name    = "archie"
      context = { cluster = "archie", user = "archie-deployer" }
    }]
  })
}
