#!/bin/bash
# Deploy Spark Kubernetes Operator
# Usage: ./deploy-spark-operator.sh [minikube|production]

set -e

ENV=${1:-minikube}
NAMESPACE="crypto-infra"
RELEASE_NAME="crypto-spark-operator"
CHART_VERSION="1.4.0"

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Deploying Spark Operator${NC}"
echo -e "${GREEN}Environment: ${ENV}${NC}"
echo -e "${GREEN}========================================${NC}"

# Validate environment
if [[ ! "$ENV" =~ ^(minikube|production)$ ]]; then
    echo -e "${RED}Error: Invalid environment. Use 'minikube' or 'production'${NC}"
    exit 1
fi

# Check if values file exists
VALUES_FILE="config/operator-values-${ENV}.yaml"
if [ ! -f "$VALUES_FILE" ]; then
    echo -e "${RED}Error: Values file not found: $VALUES_FILE${NC}"
    exit 1
fi

# Add official Helm repo if not already added
echo -e "${YELLOW}Adding official Spark Helm repository...${NC}"
if ! helm repo list | grep -q "^spark"; then
    helm repo add spark https://apache.github.io/spark-kubernetes-operator
    echo -e "${GREEN}✓ Repository added${NC}"
else
    echo -e "${GREEN}✓ Repository already exists${NC}"
fi

# Update Helm repos
echo -e "${YELLOW}Updating Helm repositories...${NC}"
helm repo update
echo -e "${GREEN}✓ Repositories updated${NC}"

# Create namespace if it doesn't exist
echo -e "${YELLOW}Ensuring namespace exists: ${NAMESPACE}${NC}"
kubectl create namespace ${NAMESPACE} 2>/dev/null || echo -e "${GREEN}✓ Namespace already exists${NC}"

# Check if release already exists
if helm list -n ${NAMESPACE} | grep -q ${RELEASE_NAME}; then
    echo -e "${YELLOW}Release already exists. Upgrading...${NC}"
    COMMAND="upgrade"
else
    echo -e "${YELLOW}Installing new release...${NC}"
    COMMAND="install"
fi

# Deploy Spark Operator
echo -e "${YELLOW}Deploying Spark Operator...${NC}"
helm ${COMMAND} ${RELEASE_NAME} spark/spark-kubernetes-operator \
    --namespace ${NAMESPACE} \
    --version ${CHART_VERSION} \
    --values ${VALUES_FILE} \
    --wait \
    --timeout 5m

echo -e "${GREEN}✓ Spark Operator deployed successfully${NC}"

# Wait for operator to be ready
echo -e "${YELLOW}Waiting for operator pods to be ready...${NC}"
kubectl wait --for=condition=ready pod \
    -l app.kubernetes.io/name=spark-kubernetes-operator \
    -n ${NAMESPACE} \
    --timeout=300s

echo -e "${GREEN}✓ Operator is ready${NC}"

# Display operator status
echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}Operator Status${NC}"
echo -e "${GREEN}========================================${NC}"
kubectl get pods -n ${NAMESPACE} -l app.kubernetes.io/name=spark-kubernetes-operator

echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}Deployment Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "Release Name: ${RELEASE_NAME}"
echo -e "Namespace: ${NAMESPACE}"
echo -e "Chart Version: ${CHART_VERSION}"
echo -e "Environment: ${ENV}"

echo -e "\n${YELLOW}Next steps:${NC}"
echo -e "1. Verify CRDs are installed:"
echo -e "   kubectl get crd | grep spark"
echo -e "2. Test with sample application:"
echo -e "   kubectl apply -f apps/spark-pi-test.yaml"
echo -e "3. Check application status:"
echo -e "   kubectl get sparkapplication -n ${NAMESPACE}"
echo -e "4. View operator logs:"
echo -e "   kubectl logs -n ${NAMESPACE} -l app.kubernetes.io/name=spark-kubernetes-operator"

# Check metrics endpoint if in production
if [ "$ENV" = "production" ]; then
    echo -e "\n${YELLOW}Metrics endpoint:${NC}"
    echo -e "   kubectl port-forward -n ${NAMESPACE} svc/${RELEASE_NAME}-metrics 19090:19090"
fi

