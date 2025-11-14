#!/bin/bash

# Script để build Spark image với code

set -e

IMAGE_NAME=${1:-"spark-crypto"}
IMAGE_TAG=${2:-"3.5.0"}
REGISTRY=${3:-""}

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}=== Building Spark Image ===${NC}"

# Build image
echo -e "${YELLOW}Building ${IMAGE_NAME}:${IMAGE_TAG}...${NC}"
docker build -t ${IMAGE_NAME}:${IMAGE_TAG} -f Dockerfile.spark ..

# Tag với registry nếu có
if [ -n "$REGISTRY" ]; then
    FULL_IMAGE="${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}"
    echo -e "${YELLOW}Tagging as ${FULL_IMAGE}...${NC}"
    docker tag ${IMAGE_NAME}:${IMAGE_TAG} ${FULL_IMAGE}
    echo -e "${YELLOW}Push image: docker push ${FULL_IMAGE}${NC}"
fi

# Nếu dùng minikube
if command -v minikube &> /dev/null; then
    echo -e "${YELLOW}Loading image into minikube...${NC}"
    minikube image load ${IMAGE_NAME}:${IMAGE_TAG}
fi

echo -e "${GREEN}✅ Image built: ${IMAGE_NAME}:${IMAGE_TAG}${NC}"

