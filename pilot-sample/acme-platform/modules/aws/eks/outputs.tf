output "cluster_name" {
  description = "EKS cluster name."
  value       = aws_eks_cluster.main.name
}
output "cluster_endpoint" {
  description = "API server endpoint."
  value       = aws_eks_cluster.main.endpoint
}
output "cluster_ca" {
  description = "Cluster CA certificate."
  value       = aws_eks_cluster.main.certificate_authority[0].data
}
