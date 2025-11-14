# Helm Charts cho Spark, Airflow và Kafka

## Tổng quan

Thư mục này chứa Helm values và scripts để deploy:
- **Kafka (Strimzi)** - Message broker
- **Spark Operator** - Để chạy Spark jobs trên Kubernetes
- **Apache Airflow** - Để orchestrate workflows

## Cấu trúc

```
Helm/
├── kafka-operator-values.yaml    # Values cho Strimzi Operator
├── kafka-cluster.yaml            # Kafka Cluster CRD
├── kafka-topics.yaml             # Kafka Topics CRD
├── deploy-kafka.sh               # Script deploy Kafka
├── spark-operator-values.yaml    # Values cho Spark Operator
├── airflow-values.yaml           # Values cho Airflow
├── spark-applications.yaml       # Spark Applications CRD
├── deploy-all.sh                 # Script deploy tự động tất cả
├── DEPLOY.md                     # Hướng dẫn Spark & Airflow
├── KAFKA_DEPLOY.md               # Hướng dẫn Kafka
└── README.md                     # File này
```

## Quick Start

### Deploy tất cả (Kafka + Spark + Airflow)

```bash
cd Helm
./deploy-all.sh
```

### Deploy từng phần

#### 1. Kafka

```bash
./deploy-kafka.sh
```

Hoặc manual:
```bash
# Thêm repo
helm repo add strimzi https://strimzi.io/charts/
helm repo update

# Install Operator
helm install strimzi-kafka-operator strimzi/strimzi-kafka-operator \
  --namespace kafka \
  --create-namespace \
  --values kafka-operator-values.yaml

# Deploy Cluster
kubectl apply -f kafka-cluster.yaml
kubectl apply -f kafka-topics.yaml
```

#### 2. Spark Operator

```bash
# Deploy bằng kubectl apply (khuyến nghị)
./deploy-spark-operator.sh

# Hoặc manual
kubectl create namespace spark
kubectl apply -f https://raw.githubusercontent.com/GoogleCloudPlatform/spark-on-k8s-operator/v1beta2-1.3.8-3.1.1/manifests/spark-operator.yaml
```

#### 2. Airflow

```bash
# Thêm repo
helm repo add apache-airflow https://airflow.apache.org
helm repo update

# Generate Fernet key
FERNET_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
# Cập nhật vào airflow-values.yaml

# Install
helm install airflow apache-airflow/airflow \
  --namespace airflow \
  --create-namespace \
  --values airflow-values.yaml
```

## Configuration

### Spark Operator

File: `spark-operator-values.yaml`

- Operator image và version
- Service account và RBAC
- Resource limits
- Webhook (optional)

### Airflow

File: `airflow-values.yaml`

- Executor type (LocalExecutor, CeleryExecutor, KubernetesExecutor)
- Webserver, Scheduler, Workers configuration
- Database (PostgreSQL)
- Redis (cho CeleryExecutor)
- DAGs và Logs persistence
- Environment variables

### Spark Applications

File: `spark-applications.yaml`

- Spark job definitions
- Driver và Executor resources
- Dependencies (JARs, Python files)
- Environment variables
- Restart policies

## Access

### Airflow UI

```bash
# Port forward
kubectl port-forward svc/airflow-webserver 8080:8080 -n airflow

# Hoặc NodePort (nếu đã config)
# http://<node-ip>:30809
```

**Default credentials:**
- Username: `admin`
- Password: (lấy từ secret)

```bash
kubectl get secret airflow-webserver-secret -n airflow \
  -o jsonpath="{.data.webserver-secret-key}" | base64 -d
```

### Spark UI

```bash
# Port forward Spark driver pod
kubectl port-forward <spark-driver-pod> 4040:4040 -n spark
# http://localhost:4040
```

## Monitoring

### Check Status

```bash
# Spark Operator
kubectl get pods -n spark
kubectl get sparkapplications -n spark

# Airflow
kubectl get pods -n airflow
kubectl get deployments -n airflow
```

### Logs

```bash
# Spark Operator
kubectl logs -f deployment/spark-operator -n spark

# Airflow
kubectl logs -f deployment/airflow-scheduler -n airflow
kubectl logs -f deployment/airflow-webserver -n airflow
```

## Troubleshooting

Xem chi tiết trong `DEPLOY.md`

## Upgrade

```bash
# Spark Operator
helm upgrade spark-operator spark-operator/spark-operator \
  --namespace spark \
  --values spark-operator-values.yaml

# Airflow
helm upgrade airflow apache-airflow/airflow \
  --namespace airflow \
  --values airflow-values.yaml
```

## Uninstall

```bash
# Spark Operator
helm uninstall spark-operator -n spark

# Airflow
helm uninstall airflow -n airflow

# Xóa namespaces
kubectl delete namespace spark
kubectl delete namespace airflow
```

## Next Steps

1. Deploy Spark Applications (xem `spark-applications.yaml`)
2. Copy DAGs vào Airflow
3. Cấu hình connections trong Airflow
4. Setup monitoring và alerting

