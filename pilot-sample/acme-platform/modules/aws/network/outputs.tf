output "vpc_id"             { description = "VPC id."                       value = aws_vpc.main.id }
output "vpc_cidr"           { description = "VPC CIDR."                     value = aws_vpc.main.cidr_block }
output "private_subnet_ids" { description = "Private subnets for workloads." value = aws_subnet.private[*].id }
output "public_subnet_ids"  { description = "Public subnets for ingress."     value = aws_subnet.public[*].id }
