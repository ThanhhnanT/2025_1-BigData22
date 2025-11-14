#!/bin/bash

# Script để build Docker images và deploy lên Kubernetes

set -e

NAMESPACE="kafka"
PRODUCER_IMAGE="binance-producer:latest"
CONSUMER_IMAGE="binance-consumer:latest"

# Màu sắc cho output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Building Docker Images ===${NC}"

# Build producer image (cùng Dockerfile, chỉ khác tag)
echo -e "${YELLOW}Building producer image...${NC}"
docker build -t ${PRODUCER_IMAGE} -f Dockerfile .

# Build consumer image (cùng Dockerfile)
echo -e "${YELLOW}Building consumer image...${NC}"
docker build -t ${CONSUMER_IMAGE} -f Dockerfile .

# Nếu dùng minikube, load images vào minikube
if command -v minikube &> /dev/null; then
    echo -e "${YELLOW}Loading images into minikube...${NC}"
    minikube image load ${PRODUCER_IMAGE}
    minikube image load ${CONSUMER_IMAGE}
fi

echo -e "${GREEN}=== Deploying to Kubernetes ===${NC}"

# Apply ConfigMap
echo -e "${YELLOW}Creating ConfigMap...${NC}"
kubectl apply -f k8s-configmap.yaml

# Apply Producer Deployment
echo -e "${YELLOW}Deploying producer...${NC}"
kubectl apply -f k8s-producer-deployment.yaml

# Apply Consumer Deployment
echo -e "${YELLOW}Deploying consumer...${NC}"
kubectl apply -f k8s-consumer-deployment.yaml

# Wait for deployments
echo -e "${YELLOW}Waiting for deployments to be ready...${NC}"
kubectl wait --for=condition=available --timeout=300s deployment/binance-producer -n ${NAMESPACE}
kubectl wait --for=condition=available --timeout=300s deployment/binance-consumer -n ${NAMESPACE}

echo -e "${GREEN}=== Deployment Complete! ===${NC}"
echo -e "Check status with:"
echo -e "  kubectl get pods -n ${NAMESPACE}"
echo -e "  kubectl logs -f deployment/binance-producer -n ${NAMESPACE}"
echo -e "  kubectl logs -f deployment/binance-consumer -n ${NAMESPACE}"

