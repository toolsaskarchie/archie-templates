data "aws_availability_zones" "available" { state = "available" }

resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true
  tags                 = merge(var.tags, { Name = "${var.project}-${var.environment}-vpc" })
}

resource "aws_subnet" "private" {
  count             = var.az_count
  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(var.vpc_cidr, 4, count.index)
  availability_zone = data.aws_availability_zones.available.names[count.index]
  # kubernetes.io/role/internal-elb is how Kubernetes DISCOVERS which subnets an
  # internal load balancer may use. It is a lookup key, not decoration: without
  # it a LoadBalancer Service fails with "could not find any suitable subnets for
  # creating the ELB" and the page never gets an address.
  tags = merge(var.tags, {
    Name                              = "${var.project}-${var.environment}-private-${count.index}"
    Tier                              = "private"
    "kubernetes.io/role/internal-elb" = "1"
  })
}

resource "aws_subnet" "public" {
  count                   = var.az_count
  vpc_id                  = aws_vpc.main.id
  cidr_block              = cidrsubnet(var.vpc_cidr, 4, count.index + 8)
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = false
  # ...and kubernetes.io/role/elb for the internet-facing one. The cluster runs
  # its nodes in the PRIVATE subnets, so these are found by tag or not at all.
  tags = merge(var.tags, {
    Name                     = "${var.project}-${var.environment}-public-${count.index}"
    Tier                     = "public"
    "kubernetes.io/role/elb" = "1"
  })
}

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id
  tags   = merge(var.tags, { Name = "${var.project}-${var.environment}-igw" })
}

resource "aws_eip" "nat" {
  count  = var.enable_nat_gateway ? var.az_count : 0
  domain = "vpc"
  tags   = merge(var.tags, { Name = "${var.project}-${var.environment}-nat-eip-${count.index}" })
}

resource "aws_nat_gateway" "main" {
  count         = var.enable_nat_gateway ? var.az_count : 0
  allocation_id = aws_eip.nat[count.index].id
  subnet_id     = aws_subnet.public[count.index].id
  tags          = merge(var.tags, { Name = "${var.project}-${var.environment}-nat-${count.index}" })
}

# ROUTES. Without these the gateways above are decoration: this module created an
# internet gateway and a NAT gateway that nothing routed to, so every subnet fell
# back to the VPC's main route table — local traffic only, no path out.
#
# It cost a 30-minute Terraform timeout to find. EKS nodes launch into the
# private subnets and must reach ECR for the CNI and kube-proxy images and the
# cluster endpoint to register; with no default route they simply never join, and
# the node group reports "Still creating" until the apply gives up. No error is
# raised anywhere, because nothing failed — the packets had nowhere to go.

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }
  tags = merge(var.tags, { Name = "${var.project}-${var.environment}-public-rt" })
}

resource "aws_route_table_association" "public" {
  count          = var.az_count
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

# One private table PER AZ, because there is one NAT gateway per AZ: a shared
# table would send every AZ's egress through a single NAT, which is both a
# cross-AZ data charge and a single point of failure for the others.
resource "aws_route_table" "private" {
  count  = var.az_count
  vpc_id = aws_vpc.main.id

  dynamic "route" {
    for_each = var.enable_nat_gateway ? [1] : []
    content {
      cidr_block     = "0.0.0.0/0"
      nat_gateway_id = aws_nat_gateway.main[count.index].id
    }
  }

  tags = merge(var.tags, { Name = "${var.project}-${var.environment}-private-rt-${count.index}" })
}

resource "aws_route_table_association" "private" {
  count          = var.az_count
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private[count.index].id
}

resource "aws_cloudwatch_log_group" "flow" {
  name              = "/aws/vpc/${var.project}-${var.environment}"
  retention_in_days = var.flow_log_retention_days
  kms_key_id        = var.kms_key_arn
  tags              = var.tags
}

resource "aws_flow_log" "main" {
  vpc_id               = aws_vpc.main.id
  traffic_type         = "ALL"
  log_destination_type = "cloud-watch-logs"
  log_destination      = aws_cloudwatch_log_group.flow.arn
  iam_role_arn         = aws_iam_role.flow.arn
  tags                 = var.tags
}

resource "aws_iam_role" "flow" {
  name = "${var.project}-${var.environment}-flowlogs"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "vpc-flow-logs.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
  tags = var.tags
}
