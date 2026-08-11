# EKS does not grant itself anything. Without AmazonEKSClusterPolicy the create
# call fails outright, and without the three node policies the group comes up
# but no node ever joins — this module declared both roles and attached nothing
# to either, so it could not have produced a working cluster.
#
# depends_on is not decoration either: the policy must be attached BEFORE the
# cluster is created, and Terraform cannot infer that from an ARN it never reads.
resource "aws_iam_role_policy_attachment" "cluster" {
  for_each   = toset(["arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"])
  role       = aws_iam_role.cluster.name
  policy_arn = each.value
}

resource "aws_iam_role_policy_attachment" "node" {
  for_each = toset([
    "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy",
    # The VPC CNI runs with the NODE's identity and assigns pod ENIs; without it
    # every pod stays stuck in ContainerCreating.
    "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy",
    "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly",
  ])
  role       = aws_iam_role.node.name
  policy_arn = each.value
}

resource "aws_eks_cluster" "main" {
  depends_on = [aws_iam_role_policy_attachment.cluster]

  name     = "${var.project}-${var.environment}"
  role_arn = aws_iam_role.cluster.arn
  version  = var.cluster_version

  vpc_config {
    subnet_ids              = var.subnet_ids
    endpoint_private_access = true
    endpoint_public_access  = true
    public_access_cidrs     = var.public_access_cidrs
  }

  encryption_config {
    provider { key_arn = var.kms_key_arn }
    resources = ["secrets"]
  }

  enabled_cluster_log_types = ["api", "audit", "authenticator", "controllerManager", "scheduler"]
  tags                      = var.tags
}

resource "aws_eks_node_group" "main" {
  depends_on = [aws_iam_role_policy_attachment.node]

  cluster_name    = aws_eks_cluster.main.name
  node_group_name = "${var.project}-${var.environment}-ng"
  node_role_arn   = aws_iam_role.node.arn
  subnet_ids      = var.subnet_ids
  instance_types  = [var.node_instance_type]
  capacity_type   = "ON_DEMAND"

  scaling_config {
    desired_size = var.node_min_size
    min_size     = var.node_min_size
    max_size     = var.node_max_size
  }
  update_config { max_unavailable = 1 }
  tags = var.tags
}

resource "aws_cloudwatch_log_group" "cluster" {
  name              = "/aws/eks/${var.project}-${var.environment}/cluster"
  retention_in_days = var.log_retention_days
  kms_key_id        = var.kms_key_arn
  tags              = var.tags
}

resource "aws_iam_role" "cluster" {
  name = "${var.project}-${var.environment}-eks-cluster"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "eks.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
  tags = var.tags
}

resource "aws_iam_role" "node" {
  name = "${var.project}-${var.environment}-eks-node"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "ec2.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
  tags = var.tags
}
