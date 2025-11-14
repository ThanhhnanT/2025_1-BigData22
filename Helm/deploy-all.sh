#!/bin/bash

# Script để deploy tất cả bằng Helm

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Namespaces
SPARK_NS="spark"
AIRFLOW_NS="airflow"

echo -e "${GREEN}=== Deploy Spark, Airflow và Kafka bằng Helm ===${NC}\n"

# Bước 1: Tạo namespaces
echo -e "${YELLOW}[1/7] Tạo namespaces...${NC}"
kubectl create namespace ${SPARK_NS} --dry-run=client -o yaml | kubectl apply -f -
kubectl create namespace ${AIRFLOW_NS} --dry-run=client -o yaml | kubectl apply -f -
kubectl create namespace kafka --dry-run=client -o yaml | kubectl apply -f -
echo -e "${GREEN}✅ Namespaces đã tạo${NC}\n"

# Bước 1.5: Deploy Kafka (nếu chưa có)
# echo -e "${YELLOW}[2/7] Deploy Kafka...${NC}"
# if [ -f "./deploy-kafka.sh" ]; then
#     ./deploy-kafka.sh
# else
#     echo -e "${YELLOW}Kafka deploy script không tìm thấy, bỏ qua...${NC}"
# fi
# echo -e "${GREEN}✅ Kafka đã deploy${NC}\n"

# Bước 2: Thêm Helm repos
echo -e "${YELLOW}[3/7] Thêm Helm repositories...${NC}"
helm repo add apache-airflow https://airflow.apache.org
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo update
echo -e "${GREEN}✅ Helm repos đã thêm${NC}\n"

# Bước 3: Deploy Spark Operator (dùng kubectl apply thay vì Helm)
echo -e "${YELLOW}[4/7] Deploy Spark Operator...${NC}"
if kubectl get deployment spark-operator -n ${SPARK_NS} &>/dev/null; then
    echo -e "${YELLOW}Spark Operator đã được cài đặt, đang update...${NC}"
    kubectl apply -f https://raw.githubusercontent.com/GoogleCloudPlatform/spark-on-k8s-operator/v1beta2-1.3.8-3.1.1/manifests/spark-operator.yaml
else
    echo -e "${YELLOW}Installing Spark Operator...${NC}"
    kubectl create namespace ${SPARK_NS} --dry-run=client -o yaml | kubectl apply -f -
    kubectl apply -f https://raw.githubusercontent.com/GoogleCloudPlatform/spark-on-k8s-operator/v1beta2-1.3.8-3.1.1/manifests/spark-operator.yaml
fi

echo -e "${YELLOW}Đợi Spark Operator khởi động...${NC}"
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=spark-operator -n ${SPARK_NS} --timeout=120s || true
echo -e "${GREEN}✅ Spark Operator đã deploy${NC}\n"

# Bước 4: Deploy Redis (nếu chưa có)
echo -e "${YELLOW}[5/7] Kiểm tra Redis...${NC}"
if ! helm list -n default | grep -q redis; then
    echo -e "${YELLOW}Deploy Redis...${NC}"
    helm install redis bitnami/redis \
        --namespace default \
        --set auth.enabled=false \
        --set persistence.enabled=true \
        --set persistence.size=1Gi
    echo -e "${GREEN}✅ Redis đã deploy${NC}\n"
else
    echo -e "${GREEN}✅ Redis đã tồn tại${NC}\n"
fi

# Bước 5: Deploy MongoDB (nếu chưa có)
echo -e "${YELLOW}[6/7] Kiểm tra MongoDB...${NC}"
if ! helm list -n default | grep -q mongodb; then
    echo -e "${YELLOW}Deploy MongoDB...${NC}"
    helm install mongodb bitnami/mongodb \
        --namespace default \
        --set auth.enabled=false \
        --set persistence.enabled=true \
        --set persistence.size=8Gi
    echo -e "${GREEN}✅ MongoDB đã deploy${NC}\n"
else
    echo -e "${GREEN}✅ MongoDB đã tồn tại${NC}\n"
fi

# Bước 6: Deploy Airflow
echo -e "${YELLOW}[7/7] Deploy Apache Airflow...${NC}"

# Generate Fernet key nếu chưa có
if ! grep -q "AIRFLOW__CORE__FERNET_KEY" airflow-values.yaml || grep -q 'value: ""' airflow-values.yaml; then
    echo -e "${YELLOW}Generating Fernet key...${NC}"
    FERNET_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>/dev/null || echo "")
    if [ -z "$FERNET_KEY" ]; then
        echo -e "${RED}⚠️  Không thể generate Fernet key. Vui lòng cập nhật thủ công trong airflow-values.yaml${NC}"
    else
        # Cập nhật Fernet key (cần sed hoặc manual)
        echo -e "${YELLOW}Fernet key: ${FERNET_KEY}${NC}"
        echo -e "${YELLOW}Vui lòng cập nhật vào airflow-values.yaml${NC}"
    fi
fi

if helm list -n ${AIRFLOW_NS} | grep -q airflow; then
    echo -e "${YELLOW}Airflow đã được cài đặt, đang upgrade...${NC}"
    helm upgrade airflow apache-airflow/airflow \
        --namespace ${AIRFLOW_NS} \
        --values airflow-values.yaml
else
    helm install airflow apache-airflow/airflow \
        --namespace ${AIRFLOW_NS} \
        --create-namespace \
        --values airflow-values.yaml
fi

echo -e "${YELLOW}Đợi Airflow khởi động (có thể mất vài phút)...${NC}"
kubectl wait --for=condition=ready pod -l component=webserver -n ${AIRFLOW_NS} --timeout=300s || true
kubectl wait --for=condition=ready pod -l component=scheduler -n ${AIRFLOW_NS} --timeout=300s || true
echo -e "${GREEN}✅ Airflow đã deploy${NC}\n"

# Tóm tắt
echo -e "${GREEN}=== Deployment Complete! ===${NC}\n"
echo -e "Kiểm tra status:"
echo -e "  kubectl get pods -n ${SPARK_NS}"
echo -e "  kubectl get pods -n ${AIRFLOW_NS}"
echo -e ""
echo -e "Truy cập Airflow UI:"
echo -e "  kubectl port-forward svc/airflow-webserver 8080:8080 -n ${AIRFLOW_NS}"
echo -e "  http://localhost:8080"
echo -e ""
echo -e "Lấy Airflow password:"
echo -e "  kubectl get secret airflow-webserver-secret -n ${AIRFLOW_NS} -o jsonpath='{.data.webserver-secret-key}' | base64 -d"

