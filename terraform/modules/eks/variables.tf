variable "cluster_name" {
  description = "Name of the EKS cluster"
  type        = string
}

variable "environment" {
  description = "Environment name"
  type        = string
}

variable "kubernetes_version" {
  description = "Kubernetes version"
  type        = string
  default     = "1.28"
}

variable "vpc_id" {
  description = "VPC ID"
  type        = string
}

variable "private_subnet_ids" {
  description = "List of private subnet IDs"
  type        = list(string)
}

variable "public_subnet_ids" {
  description = "List of public subnet IDs"
  type        = list(string)
}

variable "cluster_security_group_id" {
  description = "Security group ID for EKS cluster"
  type        = string
}

variable "nodes_security_group_id" {
  description = "Security group ID for EKS nodes"
  type        = string
}

variable "cluster_role_arn" {
  description = "IAM role ARN for EKS cluster"
  type        = string
}

variable "node_group_role_arn" {
  description = "IAM role ARN for EKS node groups"
  type        = string
}

variable "enable_public_access" {
  description = "Enable public API endpoint"
  type        = bool
  default     = true
}

variable "allowed_cidr_blocks" {
  description = "CIDR blocks allowed to access cluster"
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "node_groups_config" {
  description = "Configuration for node groups"
  type = object({
    application = object({
      instance_types = list(string)
      min_size       = number
      max_size       = number
      desired_size   = number
      capacity_type  = string
    })
    data_processing = object({
      instance_types = list(string)
      min_size       = number
      max_size       = number
      desired_size   = number
      capacity_type  = string
    })
    system = object({
      instance_types = list(string)
      min_size       = number
      max_size       = number
      desired_size   = number
      capacity_type  = string
    })
  })
}

variable "ebs_csi_driver_role_arn" {
  description = "IAM role ARN for EBS CSI Driver (IRSA)"
  type        = string
  default     = ""
}

variable "tags" {
  description = "Common tags"
  type        = map(string)
  default     = {}
}

