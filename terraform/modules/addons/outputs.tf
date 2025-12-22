output "alb_controller_service_account" {
  description = "Service account name for ALB Controller"
  value       = try(kubernetes_service_account.alb_controller["create"].metadata[0].name, "")
}

output "cluster_autoscaler_role_arn" {
  description = "IAM role ARN for Cluster Autoscaler"
  value       = try(aws_iam_role.cluster_autoscaler["create"].arn, "")
}

