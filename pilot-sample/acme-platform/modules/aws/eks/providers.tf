terraform {
  required_version = ">= 1.5"
  required_providers {
    aws        = { source = "hashicorp/aws", version = ">= 5.40" }
    kubernetes = { source = "hashicorp/kubernetes", version = ">= 2.30" }
  }
}

# The cluster this module just created, authed as its creator. aws_eks_cluster_auth
# mints a short-lived token at plan/apply time, so bootstrapping the deployer
# ServiceAccount needs no kubeconfig and no second credential.
data "aws_eks_cluster_auth" "this" {
  name = aws_eks_cluster.main.name
}

provider "kubernetes" {
  host                   = aws_eks_cluster.main.endpoint
  cluster_ca_certificate = base64decode(aws_eks_cluster.main.certificate_authority[0].data)
  token                  = data.aws_eks_cluster_auth.this.token
}
