output "alb_dns_name"      { description = "Public ALB hostname."   value = aws_lb.main.dns_name }
output "security_group_id" { description = "Task security group."   value = aws_security_group.service.id }
