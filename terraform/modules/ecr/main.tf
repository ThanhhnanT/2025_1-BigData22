locals {
  repositories = [
    "crypto-frontend-next",
    "crypto-backend-fastapi",
    "crypto-binance-producer",
    "spark-crypto",
    "airflow-crypto"
  ]

  common_tags = merge(
    var.tags,
    {
      Name = "${var.cluster_name}-ecr"
    }
  )
}

# ECR Repositories
resource "aws_ecr_repository" "repos" {
  for_each = toset(local.repositories)

  name                 = "${var.cluster_name}/${each.value}"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }

  tags = merge(
    local.common_tags,
    {
      Repository = each.value
    }
  )
}

# Lifecycle Policies
resource "aws_ecr_lifecycle_policy" "repos" {
  for_each = aws_ecr_repository.repos

  repository = each.value.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep last ${var.image_count} images"
        selection = {
          tagStatus     = "any"
          countType     = "imageCountMoreThan"
          countNumber   = var.image_count
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}

