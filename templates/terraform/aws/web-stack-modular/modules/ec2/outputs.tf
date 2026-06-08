output "instance_ids" {
  description = "IDs of the backend EC2 instances."
  value       = aws_instance.web[*].id
}

output "instance_arns" {
  description = "ARNs of the backend EC2 instances."
  value       = aws_instance.web[*].arn
}

output "private_ips" {
  description = "Private IPs of the backend EC2 instances."
  value       = aws_instance.web[*].private_ip
}
