#!/bin/bash

# Script để deploy Kafka bằng Helm

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

NAMESPACE="kafka"
OPERATOR_RELEASE="strimzi-kafka-operator"

echo -e "${GREEN}=== Deploy Kafka với Helm ===${NC}\n"

# Bước 1: Tạo namespace
echo -e "${YELLOW}[1/5] Tạo namespace...${NC}"
kubectl create namespace ${NAMESPACE} --dry-run=client -o yaml | kubectl apply -f -
echo -e "${GREEN}✅ Namespace đã tạo${NC}\n"

# Bước 2: Thêm Helm repo
echo -e "${YELLOW}[2/5] Thêm Helm repository...${NC}"
if ! helm repo list | grep -q strimzi; then
    helm repo add strimzi https://strimzi.io/charts/
    helm repo update
    echo -e "${GREEN}✅ Helm repo đã thêm${NC}\n"
else
    echo -e "${GREEN}✅ Helm repo đã tồn tại${NC}\n"
    helm repo update
fi

# Bước 3: Deploy Strimzi Operator
echo -e "${YELLOW}[3/5] Deploy Strimzi Kafka Operator...${NC}"
if helm list -n ${NAMESPACE} | grep -q ${OPERATOR_RELEASE}; then
    echo -e "${YELLOW}Operator đã được cài đặt, đang upgrade...${NC}"
    helm upgrade ${OPERATOR_RELEASE} strimzi/strimzi-kafka-operator \
        --namespace ${NAMESPACE} \
        --values kafka-operator-values.yaml
else
    helm install ${OPERATOR_RELEASE} strimzi/strimzi-kafka-operator \
        --namespace ${NAMESPACE} \
        --create-namespace \
        --values kafka-operator-values.yaml
fi

echo -e "${YELLOW}Đợi Operator khởi động...${NC}"
kubectl wait --for=condition=ready pod -l name=strimzi-cluster-operator -n ${NAMESPACE} --timeout=120s
echo -e "${GREEN}✅ Operator đã deploy${NC}\n"

# Bước 4: Deploy Kafka Cluster
echo -e "${YELLOW}[4/5] Deploy Kafka Cluster...${NC}"
if kubectl get kafka my-cluster -n ${NAMESPACE} &>/dev/null; then
    echo -e "${YELLOW}Kafka cluster đã tồn tại, đang update...${NC}"
    kubectl apply -f kafka-cluster.yaml
else
    kubectl apply -f kafka-cluster.yaml
fi

echo -e "${YELLOW}Đợi Kafka cluster khởi động (có thể mất vài phút)...${NC}"
kubectl wait --for=condition=Ready kafka/my-cluster -n ${NAMESPACE} --timeout=600s || true
echo -e "${GREEN}✅ Kafka cluster đã deploy${NC}\n"

# Bước 5: Deploy Kafka Topics
echo -e "${YELLOW}[5/5] Deploy Kafka Topics...${NC}"
kubectl apply -f kafka-topics.yaml

echo -e "${YELLOW}Đợi topics được tạo...${NC}"
sleep 10
kubectl wait --for=condition=Ready kafkatopic/crypto-kline-1m -n ${NAMESPACE} --timeout=60s || true
echo -e "${GREEN}✅ Topics đã deploy${NC}\n"

# Tóm tắt
echo -e "${GREEN}=== Deployment Complete! ===${NC}\n"
echo -e "Kiểm tra status:"
echo -e "  kubectl get pods -n ${NAMESPACE}"
echo -e "  kubectl get kafka -n ${NAMESPACE}"
echo -e "  kubectl get kafkatopic -n ${NAMESPACE}"
echo -e ""
echo -e "Kafka Bootstrap Service:"
echo -e "  kubectl get svc my-cluster-kafka-bootstrap -n ${NAMESPACE}"
echo -e ""
echo -e "Test connection:"
echo -e "  kubectl run kafka-client -it --rm --image=quay.io/strimzi/kafka:0.40.0-kafka-3.7.0 --restart=Never -- bin/kafka-topics.sh --bootstrap-server my-cluster-kafka-bootstrap:9092 --list"

