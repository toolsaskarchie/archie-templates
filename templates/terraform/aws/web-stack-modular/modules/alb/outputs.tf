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

output "target_group_arn" {
  description = "ARN of the target group attached to the ALB listener."
  value       = aws_lb_target_group.main.arn
}

output "web_security_group_id" {
  description = "Security group ID for the ALB (re-used by EC2 instances behind it)."
  value       = aws_security_group.web.id
}
