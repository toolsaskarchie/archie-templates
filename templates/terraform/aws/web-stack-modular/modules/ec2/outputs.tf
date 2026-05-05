output "instance_id" {
  description = "ID of the EC2 instance."
  value       = aws_instance.web.id
}

output "instance_arn" {
  description = "ARN of the EC2 instance."
  value       = aws_instance.web.arn
}

output "private_ip" {
  description = "Private IP of the EC2 instance."
  value       = aws_instance.web.private_ip
}
