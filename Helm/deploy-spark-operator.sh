#!/bin/bash

# Script để deploy Spark Operator bằng kubectl apply

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

NAMESPACE="spark"
SPARK_OPERATOR_VERSION="v1beta2-1.3.8-3.1.1"
MANIFEST_URL="https://raw.githubusercontent.com/GoogleCloudPlatform/spark-on-k8s-operator/${SPARK_OPERATOR_VERSION}/manifests/spark-operator.yaml"

echo -e "${GREEN}=== Deploy Spark Operator ===${NC}\n"

# Tạo namespace
echo -e "${YELLOW}[1/3] Tạo namespace...${NC}"
kubectl create namespace ${NAMESPACE} --dry-run=client -o yaml | kubectl apply -f -
echo -e "${GREEN}✅ Namespace đã tạo${NC}\n"

# Deploy Spark Operator
echo -e "${YELLOW}[2/3] Deploy Spark Operator (version: ${SPARK_OPERATOR_VERSION})...${NC}"
if kubectl get deployment spark-operator -n ${NAMESPACE} &>/dev/null; then
    echo -e "${YELLOW}Spark Operator đã tồn tại, đang update...${NC}"
    kubectl apply -f ${MANIFEST_URL}
else
    echo -e "${YELLOW}Installing Spark Operator...${NC}"
    kubectl apply -f ${MANIFEST_URL}
fi

# Đợi operator khởi động
echo -e "${YELLOW}[3/3] Đợi Spark Operator khởi động...${NC}"
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=spark-operator -n ${NAMESPACE} --timeout=120s || true

# Kiểm tra
echo -e "\n${GREEN}=== Kiểm tra ===${NC}"
kubectl get pods -n ${NAMESPACE}
kubectl get crd | grep spark

echo -e "\n${GREEN}✅ Spark Operator đã deploy thành công!${NC}"
echo -e "Kiểm tra logs:"
echo -e "  kubectl logs -f deployment/spark-operator -n ${NAMESPACE}"

