output "eks_cluster_role_arn" {
  description = "ARN of the EKS cluster IAM role"
  value       = aws_iam_role.eks_cluster.arn
}

output "eks_node_group_role_arn" {
  description = "ARN of the EKS node group IAM role"
  value       = aws_iam_role.eks_node_group.arn
}

output "alb_controller_role_arn" {
  description = "ARN of the ALB Controller IAM role (IRSA)"
  value       = var.oidc_provider_arn != "" ? aws_iam_role.alb_controller[0].arn : ""
}

output "ebs_csi_driver_role_arn" {
  description = "ARN of the EBS CSI Driver IAM role (IRSA)"
  value       = var.oidc_provider_arn != "" ? aws_iam_role.ebs_csi_driver[0].arn : ""
}

