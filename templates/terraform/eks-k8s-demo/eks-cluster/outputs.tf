output "cluster_name" {
  description = "EKS cluster name"
  value       = module.eks.cluster_name
}
output "cluster_endpoint" {
  description = "EKS cluster API endpoint"
  value       = module.eks.cluster_endpoint
}
output "cluster_certificate_authority_data" {
  description = "Base64 cluster CA certificate"
  value       = module.eks.cluster_certificate_authority_data
}
output "vpc_id" {
  description = "VPC ID"
  value       = module.vpc.vpc_id
}
output "ecr_repository_urls" {
  description = "ECR repository URLs per service"
  value       = { for name, repo in aws_ecr_repository.services : name => repo.repository_url }
}
output "kubeconfig" {
  description = "Self-contained kubeconfig (archie-deployer SA token) to register as a Kubernetes cloud account"
  value       = local.kubeconfig
  sensitive   = true
}
