locals {
  common_tags = merge(
    var.tags,
    {
      Name = var.cluster_name
    }
  )
}

# OIDC Provider
data "tls_certificate" "eks" {
  url = aws_eks_cluster.main.identity[0].oidc[0].issuer
}

resource "aws_iam_openid_connect_provider" "main" {
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = [data.tls_certificate.eks.certificates[0].sha1_fingerprint]
  url             = aws_eks_cluster.main.identity[0].oidc[0].issuer

  tags = local.common_tags
}

# EKS Cluster
resource "aws_eks_cluster" "main" {
  name     = var.cluster_name
  role_arn = var.cluster_role_arn
  version  = var.kubernetes_version

  vpc_config {
    subnet_ids              = concat(var.private_subnet_ids, var.public_subnet_ids)
    security_group_ids      = [var.cluster_security_group_id]
    endpoint_private_access = true
    endpoint_public_access  = var.enable_public_access
    public_access_cidrs     = var.allowed_cidr_blocks
  }

  enabled_cluster_log_types = ["api", "audit", "authenticator", "controllerManager", "scheduler"]

  encryption_config {
    provider {
      key_arn = aws_kms_key.eks.arn
    }
    resources = ["secrets"]
  }

  depends_on = [
    aws_cloudwatch_log_group.eks_cluster
  ]

  tags = local.common_tags
}

# KMS Key for EKS encryption
resource "aws_kms_key" "eks" {
  description             = "EKS cluster encryption key"
  deletion_window_in_days = 7
  enable_key_rotation     = true

  tags = merge(
    local.common_tags,
    {
      Name = "${var.cluster_name}-eks-key"
    }
  )
}

resource "aws_kms_alias" "eks" {
  name          = "alias/${var.cluster_name}-eks"
  target_key_id = aws_kms_key.eks.key_id
}

# CloudWatch Log Group
resource "aws_cloudwatch_log_group" "eks_cluster" {
  name              = "/aws/eks/${var.cluster_name}/cluster"
  retention_in_days  = 7

  tags = local.common_tags
}

# Managed Node Group - Application
resource "aws_eks_node_group" "application" {
  cluster_name    = aws_eks_cluster.main.name
  node_group_name = "${var.cluster_name}-application"
  node_role_arn   = var.node_group_role_arn
  subnet_ids      = var.private_subnet_ids

  instance_types = var.node_groups_config.application.instance_types
  capacity_type  = var.node_groups_config.application.capacity_type

  scaling_config {
    desired_size = var.node_groups_config.application.desired_size
    min_size     = var.node_groups_config.application.min_size
    max_size     = var.node_groups_config.application.max_size
  }

  update_config {
    max_unavailable = 1
  }

  labels = {
    role = "application"
    environment = var.environment
  }

  remote_access {
    ec2_ssh_key = null
  }

  tags = merge(
    local.common_tags,
    {
      Name = "${var.cluster_name}-application-node"
      "k8s.io/cluster-autoscaler/enabled" = "true"
      "k8s.io/cluster-autoscaler/${var.cluster_name}" = "owned"
    }
  )

  depends_on = [
    aws_iam_role_policy_attachment.eks_worker_node_policy,
    aws_iam_role_policy_attachment.eks_cni_policy,
    aws_iam_role_policy_attachment.eks_container_registry_policy,
  ]
}

# Managed Node Group - Data Processing
resource "aws_eks_node_group" "data_processing" {
  cluster_name    = aws_eks_cluster.main.name
  node_group_name = "${var.cluster_name}-data-processing"
  node_role_arn   = var.node_group_role_arn
  subnet_ids      = var.private_subnet_ids

  instance_types = var.node_groups_config.data_processing.instance_types
  capacity_type  = var.node_groups_config.data_processing.capacity_type

  scaling_config {
    desired_size = var.node_groups_config.data_processing.desired_size
    min_size     = var.node_groups_config.data_processing.min_size
    max_size     = var.node_groups_config.data_processing.max_size
  }

  update_config {
    max_unavailable = 1
  }

  labels = {
    role = "data-processing"
    environment = var.environment
  }

  remote_access {
    ec2_ssh_key = null
  }

  tags = merge(
    local.common_tags,
    {
      Name = "${var.cluster_name}-data-processing-node"
      "k8s.io/cluster-autoscaler/enabled" = "true"
      "k8s.io/cluster-autoscaler/${var.cluster_name}" = "owned"
    }
  )

  depends_on = [
    aws_iam_role_policy_attachment.eks_worker_node_policy,
    aws_iam_role_policy_attachment.eks_cni_policy,
    aws_iam_role_policy_attachment.eks_container_registry_policy,
  ]
}

# Managed Node Group - System
resource "aws_eks_node_group" "system" {
  cluster_name    = aws_eks_cluster.main.name
  node_group_name = "${var.cluster_name}-system"
  node_role_arn   = var.node_group_role_arn
  subnet_ids      = var.private_subnet_ids

  instance_types = var.node_groups_config.system.instance_types
  capacity_type  = var.node_groups_config.system.capacity_type

  scaling_config {
    desired_size = var.node_groups_config.system.desired_size
    min_size     = var.node_groups_config.system.min_size
    max_size     = var.node_groups_config.system.max_size
  }

  update_config {
    max_unavailable = 1
  }

  labels = {
    role = "system"
    environment = var.environment
  }

  remote_access {
    ec2_ssh_key = null
  }

  tags = merge(
    local.common_tags,
    {
      Name = "${var.cluster_name}-system-node"
      "k8s.io/cluster-autoscaler/enabled" = "true"
      "k8s.io/cluster-autoscaler/${var.cluster_name}" = "owned"
    }
  )

  depends_on = [
    aws_iam_role_policy_attachment.eks_worker_node_policy,
    aws_iam_role_policy_attachment.eks_cni_policy,
    aws_iam_role_policy_attachment.eks_container_registry_policy,
  ]
}

# These are referenced in node groups but defined in IAM module
# We'll use data sources or pass them as variables
data "aws_iam_role" "node_group" {
  name = split("/", var.node_group_role_arn)[1]
}

resource "aws_iam_role_policy_attachment" "eks_worker_node_policy" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy"
  role       = data.aws_iam_role.node_group.name
}

resource "aws_iam_role_policy_attachment" "eks_cni_policy" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy"
  role       = data.aws_iam_role.node_group.name
}

resource "aws_iam_role_policy_attachment" "eks_container_registry_policy" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
  role       = data.aws_iam_role.node_group.name
}

# EKS Add-ons
resource "aws_eks_addon" "vpc_cni" {
  cluster_name = aws_eks_cluster.main.name
  addon_name   = "vpc-cni"
  addon_version = "v1.14.1-eksbuild.1"

  tags = local.common_tags
}

resource "aws_eks_addon" "kube_proxy" {
  cluster_name = aws_eks_cluster.main.name
  addon_name   = "kube-proxy"
  addon_version = "v1.28.1-eksbuild.1"

  tags = local.common_tags
}

resource "aws_eks_addon" "coredns" {
  cluster_name = aws_eks_cluster.main.name
  addon_name   = "coredns"
  addon_version = "v1.10.1-eksbuild.1"

  tags = local.common_tags
}

resource "aws_eks_addon" "ebs_csi" {
  count = var.ebs_csi_driver_role_arn != "" ? 1 : 0

  cluster_name             = aws_eks_cluster.main.name
  addon_name               = "aws-ebs-csi-driver"
  addon_version            = "v1.20.0-eksbuild.1"
  service_account_role_arn = var.ebs_csi_driver_role_arn

  tags = local.common_tags
}

