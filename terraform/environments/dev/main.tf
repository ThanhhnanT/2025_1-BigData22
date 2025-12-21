module "crypto_eks" {
  source = "../../"

  aws_region         = "ap-southeast-1"
  cluster_name       = "crypto-eks-dev"
  environment        = "dev"
  kubernetes_version = "1.28"
  vpc_cidr           = "10.0.0.0/16"

  enable_nat_gateway  = true
  single_nat_gateway  = false
  enable_vpc_endpoints = true

  enable_public_access = true
  allowed_cidr_blocks   = ["0.0.0.0/0"]

  node_instance_types = {
    application     = ["t3.large"]
    data_processing = ["t3.xlarge"]
    system          = ["t3.medium"]
  }

  node_groups_config = {
    application = {
      min_size     = 2
      max_size     = 5
      desired_size = 2
    }
    data_processing = {
      min_size     = 2
      max_size     = 4
      desired_size = 2
    }
    system = {
      min_size     = 2
      max_size     = 3
      desired_size = 2
    }
  }

  tags = {
    Project     = "Crypto-Trading-Platform"
    ManagedBy   = "Terraform"
    Environment = "dev"
    Team        = "BigData"
  }
}

