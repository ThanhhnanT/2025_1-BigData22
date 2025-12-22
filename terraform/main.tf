provider "aws" {
  region = var.aws_region

  default_tags {
    tags = merge(
      var.tags,
      {
        Environment = var.environment
        ManagedBy   = "Terraform"
      }
    )
  }
}

# VPC Module
module "vpc" {
  source = "./modules/vpc"

  vpc_cidr          = var.vpc_cidr
  availability_zones = var.availability_zones
  environment       = var.environment
  cluster_name      = var.cluster_name
  enable_nat_gateway = var.enable_nat_gateway
  single_nat_gateway = var.single_nat_gateway
  enable_vpc_endpoints = var.enable_vpc_endpoints
  tags              = var.tags
}

# IAM Module
module "iam" {
  source = "./modules/iam"

  cluster_name = var.cluster_name
  environment  = var.environment
  # IRSA is disabled in this base IAM module; it's handled in the separate iam_irsa module
  enable_irsa  = false
  tags         = var.tags
}

# ECR Module
module "ecr" {
  source = "./modules/ecr"

  cluster_name = var.cluster_name
  environment  = var.environment
  image_count  = 10
  tags         = var.tags
}

# EKS Module
module "eks" {
  source = "./modules/eks"

  cluster_name              = var.cluster_name
  environment               = var.environment
  kubernetes_version        = var.kubernetes_version
  vpc_id                    = module.vpc.vpc_id
  private_subnet_ids        = module.vpc.private_subnet_ids
  public_subnet_ids         = module.vpc.public_subnet_ids
  cluster_security_group_id = module.vpc.eks_cluster_security_group_id
  nodes_security_group_id   = module.vpc.eks_nodes_security_group_id
  cluster_role_arn          = module.iam.eks_cluster_role_arn
  node_group_role_arn       = module.iam.eks_node_group_role_arn
  enable_public_access      = var.enable_public_access
  allowed_cidr_blocks       = var.allowed_cidr_blocks
  ebs_csi_driver_role_arn   = ""  # Will be set after IAM IRSA module creates the role

  node_groups_config = {
    application = {
      instance_types = var.node_instance_types.application
      min_size       = var.node_groups_config.application.min_size
      max_size       = var.node_groups_config.application.max_size
      desired_size   = var.node_groups_config.application.desired_size
      capacity_type  = "ON_DEMAND"
    }
    data_processing = {
      instance_types = var.node_instance_types.data_processing
      min_size       = var.node_groups_config.data_processing.min_size
      max_size       = var.node_groups_config.data_processing.max_size
      desired_size   = var.node_groups_config.data_processing.desired_size
      capacity_type  = "ON_DEMAND"
    }
    system = {
      instance_types = var.node_instance_types.system
      min_size       = var.node_groups_config.system.min_size
      max_size       = var.node_groups_config.system.max_size
      desired_size   = var.node_groups_config.system.desired_size
      capacity_type  = "ON_DEMAND"
    }
  }

  tags = var.tags

  depends_on = [
    module.vpc,
    module.iam
  ]
}

# IRSA Roles (created after EKS cluster with OIDC provider)
module "iam_irsa" {
  source = "./modules/iam"

  cluster_name      = var.cluster_name
  environment       = var.environment
  enable_irsa       = true
  oidc_provider_arn = module.eks.oidc_provider_arn
  oidc_provider_url = module.eks.oidc_provider_url
  tags              = var.tags

  depends_on = [module.eks]
}

# Update EBS CSI addon with IRSA role (requires separate apply after IAM IRSA is created)
# Note: This is a limitation - EBS CSI addon needs to be created/updated in a second terraform apply
# Or you can manually update it: aws eks update-addon --cluster-name <cluster> --addon-name aws-ebs-csi-driver --service-account-role-arn <arn>

# Add-ons Module
module "addons" {
  source = "./modules/addons"

  cluster_name            = var.cluster_name
  cluster_endpoint        = module.eks.cluster_endpoint
  cluster_ca_certificate  = module.eks.cluster_certificate_authority_data
  alb_controller_role_arn  = module.iam_irsa.alb_controller_role_arn
  oidc_provider_arn       = module.eks.oidc_provider_arn
  oidc_provider_url       = module.eks.oidc_provider_url
  vpc_id                  = module.vpc.vpc_id
  environment             = var.environment
  tags                    = var.tags
}

