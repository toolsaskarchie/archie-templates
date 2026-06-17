output "alb_url" {
  description = "Full URL to reach the load balancer."
  value       = module.web.alb_url
}

output "alb_dns_name" {
  description = "Public DNS name of the ALB."
  value       = module.web.alb_dns_name
}

output "alb_security_group_id" {
  description = "ALB security group — the resource the drift demo edits (port 80/443 from allowed_cidrs)."
  value       = module.web.alb_security_group_id
}

output "instance_ids" {
  description = "Backend EC2 instance IDs."
  value       = module.web.instance_ids
}

output "instance_type" {
  description = "Effective EC2 size — governed."
  value       = module.web.instance_type
}

output "instance_count" {
  description = "Effective backend instance count — governed."
  value       = module.web.instance_count
}

output "vpc_cidr" {
  description = "Effective VPC CIDR — governed."
  value       = module.web.vpc_cidr
}
