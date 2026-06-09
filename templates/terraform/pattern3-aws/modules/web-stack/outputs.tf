output "vpc_id" {
  description = "ID of the created VPC."
  value       = aws_vpc.main.id
}

output "public_subnet_ids" {
  description = "IDs of the public subnets (one per AZ)."
  value       = aws_subnet.public[*].id
}

output "alb_dns" {
  description = "Public DNS name of the Application Load Balancer."
  value       = aws_lb.main.dns_name
}

output "alb_dns_name" {
  description = "Public DNS name of the Application Load Balancer (Pulumi-aliased name)."
  value       = aws_lb.main.dns_name
}

output "alb_url" {
  description = "Full http(s):// URL to reach the ALB."
  value       = var.enable_https && var.certificate_arn != "" ? "https://${aws_lb.main.dns_name}" : "http://${aws_lb.main.dns_name}"
}

output "alb_arn" {
  description = "ARN of the Application Load Balancer."
  value       = aws_lb.main.arn
}

output "target_group_arn" {
  description = "ARN of the target group attached to the ALB listener."
  value       = aws_lb_target_group.main.arn
}

output "alb_security_group_id" {
  description = "ID of the ALB-facing security group."
  value       = aws_security_group.alb.id
}

output "backend_security_group_id" {
  description = "ID of the backend security group."
  value       = aws_security_group.backend.id
}

output "instance_ids" {
  description = "IDs of the backend EC2 instances."
  value       = aws_instance.web[*].id
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
  description = "Per-instance EC2 sizes (one entry per backend)."
  value       = aws_instance.web[*].instance_type
}

output "instance_private_ips" {
  description = "Private IPs of each backend EC2 instance."
  value       = aws_instance.web[*].private_ip
}

output "instance_availability_zones" {
  description = "AZ each backend instance landed in."
  value       = aws_instance.web[*].availability_zone
}

output "instance_amis" {
  description = "AMI ID each backend instance booted from."
  value       = aws_instance.web[*].ami
}

output "vpc_cidr" {
  description = "CIDR block of the created VPC."
  value       = aws_vpc.main.cidr_block
}
