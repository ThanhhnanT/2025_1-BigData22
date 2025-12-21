#!/bin/bash
set -e

# Script to build and push Docker images to AWS ECR
# Usage: ./build-and-push-images.sh [REGION] [CLUSTER_NAME]

REGION="${1:-ap-southeast-1}"
CLUSTER_NAME="${2:-crypto-eks}"
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

if [ -z "$AWS_ACCOUNT_ID" ]; then
    echo "Error: Unable to get AWS Account ID. Make sure AWS CLI is configured."
    exit 1
fi

ECR_BASE_URL="${AWS_ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"

echo "=========================================="
echo "Building and pushing Docker images to ECR"
echo "=========================================="
echo "Region: $REGION"
echo "Cluster Name: $CLUSTER_NAME"
echo "ECR Base URL: $ECR_BASE_URL"
echo ""

# Login to ECR
echo "Logging in to ECR..."
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $ECR_BASE_URL

# Function to build and push image
build_and_push() {
    local image_name=$1
    local dockerfile_path=$2
    local context_path=$3
    
    echo ""
    echo "Building $image_name..."
    docker build -t $image_name:latest -f $dockerfile_path $context_path
    
    echo "Tagging $image_name..."
    docker tag $image_name:latest $ECR_BASE_URL/$CLUSTER_NAME/$image_name:latest
    
    echo "Pushing $image_name to ECR..."
    docker push $ECR_BASE_URL/$CLUSTER_NAME/$image_name:latest
    
    echo "✅ Successfully pushed $image_name"
}

# Build and push images
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "Project root: $PROJECT_ROOT"
echo ""

# Frontend
if [ -f "$PROJECT_ROOT/frontend/Dockerfile" ]; then
    build_and_push "crypto-frontend-next" \
        "$PROJECT_ROOT/frontend/Dockerfile" \
        "$PROJECT_ROOT/frontend"
else
    echo "⚠️  Frontend Dockerfile not found, skipping..."
fi

# Backend
if [ -f "$PROJECT_ROOT/backend_fastapi/Dockerfile" ]; then
    build_and_push "crypto-backend-fastapi" \
        "$PROJECT_ROOT/backend_fastapi/Dockerfile" \
        "$PROJECT_ROOT/backend_fastapi"
else
    echo "⚠️  Backend Dockerfile not found, skipping..."
fi

# Kafka Producer
if [ -f "$PROJECT_ROOT/Kafka/Dockerfile" ]; then
    build_and_push "crypto-binance-producer" \
        "$PROJECT_ROOT/Kafka/Dockerfile" \
        "$PROJECT_ROOT/Kafka"
else
    echo "⚠️  Kafka Dockerfile not found, skipping..."
fi

# Spark
if [ -f "$PROJECT_ROOT/Spark/Dockerfile" ]; then
    build_and_push "spark-crypto" \
        "$PROJECT_ROOT/Spark/Dockerfile" \
        "$PROJECT_ROOT/Spark"
else
    echo "⚠️  Spark Dockerfile not found, skipping..."
fi

# Airflow
if [ -f "$PROJECT_ROOT/airflow/Dockerfile" ]; then
    build_and_push "airflow-crypto" \
        "$PROJECT_ROOT/airflow/Dockerfile" \
        "$PROJECT_ROOT/airflow"
else
    echo "⚠️  Airflow Dockerfile not found, skipping..."
fi

echo ""
echo "=========================================="
echo "✅ All images built and pushed successfully!"
echo "=========================================="
echo ""
echo "ECR Repository URLs:"
echo "  Frontend:  $ECR_BASE_URL/$CLUSTER_NAME/crypto-frontend-next:latest"
echo "  Backend:  $ECR_BASE_URL/$CLUSTER_NAME/crypto-backend-fastapi:latest"
echo "  Kafka:    $ECR_BASE_URL/$CLUSTER_NAME/crypto-binance-producer:latest"
echo "  Spark:    $ECR_BASE_URL/$CLUSTER_NAME/spark-crypto:latest"
echo "  Airflow:  $ECR_BASE_URL/$CLUSTER_NAME/airflow-crypto:latest"
echo ""
echo "Update your Kubernetes manifests with these image URLs."

