output "alb_controller_service_account" {
  description = "Service account name for ALB Controller"
  value       = var.alb_controller_role_arn != "" ? kubernetes_service_account.alb_controller[0].metadata[0].name : ""
}

output "cluster_autoscaler_role_arn" {
  description = "IAM role ARN for Cluster Autoscaler"
  value       = length(aws_iam_role.cluster_autoscaler) > 0 ? aws_iam_role.cluster_autoscaler[0].arn : ""
}

