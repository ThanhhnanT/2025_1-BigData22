variable "aws_region" {
  description = "AWS region for resources"
  type        = string
  default     = "ap-southeast-1"
}

variable "cluster_name" {
  description = "Name of the EKS cluster"
  type        = string
  default     = "crypto-eks"
}

variable "environment" {
  description = "Environment name (dev/staging/prod)"
  type        = string
  default     = "dev"
}

variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "List of availability zones"
  type        = list(string)
  default     = []
}

variable "enable_public_access" {
  description = "Enable public API endpoint for EKS cluster"
  type        = bool
  default     = true
}

variable "allowed_cidr_blocks" {
  description = "CIDR blocks allowed to access EKS API endpoint"
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "node_instance_types" {
  description = "Instance types for node groups"
  type = object({
    application = list(string)
    data_processing = list(string)
    system = list(string)
  })
  default = {
    application     = ["t3.large"]
    data_processing = ["t3.xlarge"]
    system          = ["t3.medium"]
  }
}

variable "node_groups_config" {
  description = "Configuration for node groups"
  type = object({
    application = object({
      min_size     = number
      max_size     = number
      desired_size = number
    })
    data_processing = object({
      min_size     = number
      max_size     = number
      desired_size = number
    })
    system = object({
      min_size     = number
      max_size     = number
      desired_size = number
    })
  })
  default = {
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
}

variable "kubernetes_version" {
  description = "Kubernetes version for EKS cluster"
  type        = string
  default     = "1.28"
}

variable "tags" {
  description = "Common tags for all resources"
  type        = map(string)
  default = {
    Project     = "Crypto-Trading-Platform"
    ManagedBy   = "Terraform"
    Environment = "dev"
  }
}

variable "enable_nat_gateway" {
  description = "Enable NAT Gateway for private subnets"
  type        = bool
  default     = true
}

variable "single_nat_gateway" {
  description = "Use single NAT Gateway for cost optimization"
  type        = bool
  default     = false
}

variable "enable_vpc_endpoints" {
  description = "Enable VPC endpoints for AWS services"
  type        = bool
  default     = true
}

