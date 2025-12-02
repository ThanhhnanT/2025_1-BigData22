#!/bin/bash
# Deploy Spark Applications
# Usage: ./deploy-spark-app.sh [app-name] [minikube|production]

set -e

APP=${1}
ENV=${2:-minikube}
NAMESPACE="crypto-infra"

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Deploying Spark Application${NC}"
echo -e "${GREEN}========================================${NC}"

# Validate inputs
if [ -z "$APP" ]; then
    echo -e "${RED}Error: Application name required${NC}"
    echo -e "Usage: $0 [app-name] [minikube|production]"
    echo -e "\nAvailable applications:"
    echo -e "  - test           : Simple Spark Pi test"
    echo -e "  - streaming      : Crypto streaming aggregator"
    exit 1
fi

if [[ ! "$ENV" =~ ^(minikube|production)$ ]]; then
    echo -e "${RED}Error: Invalid environment. Use 'minikube' or 'production'${NC}"
    exit 1
fi

# Map app names to files
case "$APP" in
    test)
        APP_FILE="apps/spark-pi-test.yaml"
        ;;
    streaming)
        APP_FILE="apps/streaming/crypto-streaming-${ENV}.yaml"
        ;;
    *)
        echo -e "${RED}Error: Unknown application: $APP${NC}"
        exit 1
        ;;
esac

# Check if file exists
if [ ! -f "$APP_FILE" ]; then
    echo -e "${RED}Error: Application file not found: $APP_FILE${NC}"
    exit 1
fi

echo -e "Application: ${APP}"
echo -e "Environment: ${ENV}"
echo -e "File: ${APP_FILE}"
echo -e "Namespace: ${NAMESPACE}"

# Verify Spark Operator is running
echo -e "\n${YELLOW}Verifying Spark Operator...${NC}"
if ! kubectl get deployment -n ${NAMESPACE} -l app.kubernetes.io/name=spark-kubernetes-operator &>/dev/null; then
    echo -e "${RED}Error: Spark Operator not found. Please deploy it first:${NC}"
    echo -e "  ./deploy-spark-operator.sh ${ENV}"
    exit 1
fi

READY=$(kubectl get deployment -n ${NAMESPACE} -l app.kubernetes.io/name=spark-kubernetes-operator -o jsonpath='{.items[0].status.readyReplicas}')
if [ -z "$READY" ] || [ "$READY" -eq 0 ]; then
    echo -e "${RED}Error: Spark Operator is not ready${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Spark Operator is running${NC}"

# Deploy application
echo -e "\n${YELLOW}Deploying application...${NC}"
kubectl apply -f ${APP_FILE}
echo -e "${GREEN}✓ Application submitted${NC}"

# Wait a bit for the application to be created
sleep 3

# Get application name from the file
APP_NAME=$(grep "name:" ${APP_FILE} | head -1 | awk '{print $2}')

echo -e "\n${YELLOW}Waiting for application to start...${NC}"
echo -e "Application name: ${APP_NAME}"

# Monitor application status
echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}Application Status${NC}"
echo -e "${GREEN}========================================${NC}"

for i in {1..30}; do
    STATE=$(kubectl get sparkapplication ${APP_NAME} -n ${NAMESPACE} -o jsonpath='{.status.applicationState.state}' 2>/dev/null || echo "UNKNOWN")
    echo -e "Status: ${STATE} (${i}/30)"
    
    if [ "$STATE" = "COMPLETED" ]; then
        echo -e "${GREEN}✓ Application completed successfully${NC}"
        break
    elif [ "$STATE" = "FAILED" ]; then
        echo -e "${RED}✗ Application failed${NC}"
        break
    elif [ "$STATE" = "RUNNING" ]; then
        echo -e "${GREEN}✓ Application is running${NC}"
        break
    fi
    
    sleep 2
done

# Show pods
echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}Application Pods${NC}"
echo -e "${GREEN}========================================${NC}"
kubectl get pods -n ${NAMESPACE} -l spark-app-name=${APP_NAME}

# Helpful commands
echo -e "\n${YELLOW}Useful commands:${NC}"
echo -e "Check application status:"
echo -e "  kubectl get sparkapplication ${APP_NAME} -n ${NAMESPACE}"
echo -e "  kubectl describe sparkapplication ${APP_NAME} -n ${NAMESPACE}"
echo -e ""
echo -e "View driver logs:"
echo -e "  kubectl logs -n ${NAMESPACE} ${APP_NAME}-driver"
echo -e ""
echo -e "View all application pods:"
echo -e "  kubectl get pods -n ${NAMESPACE} -l spark-app-name=${APP_NAME}"
echo -e ""
echo -e "Port-forward to Spark UI (if running):"
echo -e "  kubectl port-forward -n ${NAMESPACE} ${APP_NAME}-driver 4040:4040"
echo -e ""
echo -e "Delete application:"
echo -e "  kubectl delete sparkapplication ${APP_NAME} -n ${NAMESPACE}"

