output "alb_arn" {
  description = "ARN of the Application Load Balancer."
  value       = aws_lb.main.arn
}

output "alb_dns" {
  description = "Public DNS name of the ALB."
  value       = aws_lb.main.dns_name
}

output "alb_zone_id" {
  description = "Hosted zone ID of the ALB (for Route53 alias records)."
  value       = aws_lb.main.zone_id
}

output "alb_url" {
  description = "Full http(s):// URL to reach the ALB on the default listener."
  value       = var.enable_https && var.certificate_arn != "" ? "https://${aws_lb.main.dns_name}" : "http://${aws_lb.main.dns_name}"
}

output "target_group_arn" {
  description = "ARN of the target group attached to the ALB listener."
  value       = aws_lb_target_group.main.arn
}

output "alb_security_group_id" {
  description = "ID of the ALB-facing security group (open to allowed_cidrs)."
  value       = aws_security_group.alb.id
}

output "backend_security_group_id" {
  description = "ID of the backend security group (only accepts traffic from the ALB SG)."
  value       = aws_security_group.backend.id
}
