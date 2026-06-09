output "vpc_id" {
  description = "ID of the created VPC."
  value       = module.vpc.vpc_id
}

output "public_subnet_ids" {
  description = "IDs of the public subnets (one per AZ)."
  value       = module.vpc.public_subnet_ids
}

output "alb_dns" {
  description = "Public DNS name of the Application Load Balancer."
  value       = module.alb.alb_dns
}

output "alb_dns_name" {
  description = "Public DNS name of the Application Load Balancer (Pulumi-aliased name)."
  value       = module.alb.alb_dns
}

output "alb_url" {
  description = "Full http(s) URL to reach the ALB."
  value       = module.alb.alb_url
}

output "alb_arn" {
  description = "ARN of the Application Load Balancer."
  value       = module.alb.alb_arn
}

output "target_group_arn" {
  description = "ARN of the target group attached to the ALB listener."
  value       = module.alb.target_group_arn
}

output "alb_security_group_id" {
  description = "ID of the ALB-facing security group (port 80/443 from allowed_cidrs)."
  value       = module.alb.alb_security_group_id
}

output "backend_security_group_id" {
  description = "ID of the backend security group (target_port from ALB SG only)."
  value       = module.alb.backend_security_group_id
}

output "instance_ids" {
  description = "IDs of the backend EC2 instances."
  value       = module.ec2.instance_ids
}

output "instance_type" {
  description = "EC2 instance size (same for every backend instance)."
  value       = var.instance_type
}

output "instance_count" {
  description = "Number of backend EC2 instances launched."
  value       = var.ec2_instance_count
}

output "instance_types" {
  description = "Per-instance EC2 sizes."
  value       = module.ec2.instance_types
}

output "instance_private_ips" {
  description = "Private IPs of each backend EC2 instance."
  value       = module.ec2.private_ips
}

output "instance_availability_zones" {
  description = "AZ each backend instance landed in."
  value       = module.ec2.availability_zones
}

output "instance_amis" {
  description = "AMI ID each backend instance booted from."
  value       = module.ec2.amis
}

output "vpc_cidr" {
  description = "CIDR block of the created VPC."
  value       = var.vpc_cidr
}
