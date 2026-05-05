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

output "alb_arn" {
  description = "ARN of the Application Load Balancer."
  value       = module.alb.alb_arn
}

output "instance_id" {
  description = "ID of the backend EC2 instance."
  value       = module.ec2.instance_id
}
