output "alb_arn" {
  description = "ARN of the Application Load Balancer."
  value       = module.web.alb_arn
}

output "alb_dns_name" {
  description = "Public DNS of the ALB."
  value       = module.web.alb_dns_name
}

output "vpc_id" {
  description = "ID of the VPC."
  value       = module.web.vpc_id
}
