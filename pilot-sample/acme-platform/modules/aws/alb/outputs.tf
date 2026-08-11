// What this component PUBLISHES. Archie parses these straight out of the HCL,
// so anything named here is something a sibling component can be wired to.

output "alb_dns_name" {
  description = "Public hostname AWS assigns — the default domain the ticket asked for."
  value       = aws_lb.main.dns_name
}
output "url" {
  description = "Ready-to-click address for this load balancer."
  value       = "http://${aws_lb.main.dns_name}"
}
output "alb_arn" {
  description = "Load balancer ARN."
  value       = aws_lb.main.arn
}
output "alb_zone_id" {
  description = "Hosted zone id, for an alias record in front of it."
  value       = aws_lb.main.zone_id
}
output "target_group_arn" {
  description = "Register a service here to receive traffic on /app."
  value       = aws_lb_target_group.app.arn
}
output "security_group_id" {
  description = "Load balancer security group — allow it into your service SG."
  value       = aws_security_group.alb.id
}
output "listener_arn" {
  description = "Listener ARN, for attaching additional rules."
  value       = aws_lb_listener.main.arn
}
