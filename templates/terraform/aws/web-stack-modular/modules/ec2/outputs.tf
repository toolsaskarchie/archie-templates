output "instance_ids" {
  description = "IDs of the backend EC2 instances."
  value       = aws_instance.web[*].id
}

output "instance_arns" {
  description = "ARNs of the backend EC2 instances."
  value       = aws_instance.web[*].arn
}

output "instance_types" {
  description = "Per-instance EC2 sizes."
  value       = aws_instance.web[*].instance_type
}

output "private_ips" {
  description = "Private IPs of the backend EC2 instances."
  value       = aws_instance.web[*].private_ip
}

output "availability_zones" {
  description = "AZ each backend instance landed in."
  value       = aws_instance.web[*].availability_zone
}

output "amis" {
  description = "AMI ID each backend instance booted from."
  value       = aws_instance.web[*].ami
}
