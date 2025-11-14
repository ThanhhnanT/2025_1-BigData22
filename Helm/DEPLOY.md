# Hướng dẫn Deploy Spark và Airflow bằng Helm

## Tổng quan

Sử dụng Helm để deploy:
1. **Spark Operator** - Để chạy Spark jobs trên Kubernetes
2. **Apache Airflow** - Để orchestrate workflows

## Yêu cầu

- Kubernetes cluster (Minikube hoặc production)
- Helm 3.x đã cài đặt
- kubectl đã cấu hình
- Đủ resources (CPU, Memory)

## Bước 1: Tạo Namespaces

```bash
# Tạo namespaces
kubectl create namespace spark
kubectl create namespace airflow
```

## Bước 2: Deploy Spark Operator

### 2.1. Deploy bằng kubectl apply (Khuyến nghị)

```bash
# Tạo namespace
kubectl create namespace spark

# Deploy Spark Operator
kubectl apply -f https://raw.githubusercontent.com/GoogleCloudPlatform/spark-on-k8s-operator/v1beta2-1.3.8-3.1.1/manifests/spark-operator.yaml
```

Hoặc dùng script:
```bash
./deploy-spark-operator.sh
```

### 2.2. Hoặc dùng Helm (nếu có repository)

```bash
# Thêm repo (nếu có)
helm repo add spark-operator <repository-url>
helm repo update

# Install
helm install spark-operator spark-operator/spark-operator \
  --namespace spark \
  --create-namespace \
  --values spark-operator-values.yaml
```

### 2.3. Kiểm tra

```bash
# Kiểm tra pods
kubectl get pods -n spark

# Kiểm tra CRD
kubectl get crd | grep spark

# Xem logs
kubectl logs -f deployment/spark-operator -n spark
```

## Bước 3: Deploy Apache Airflow

### 3.1. Thêm Helm repo

```bash
helm repo add apache-airflow https://airflow.apache.org
helm repo update
```

### 3.2. Generate Fernet Key (cho Airflow)

```bash
# Generate Fernet key
FERNET_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
echo "FERNET_KEY: $FERNET_KEY"

# Cập nhật vào airflow-values.yaml
# env:
#   - name: AIRFLOW__CORE__FERNET_KEY
#     value: "<FERNET_KEY>"
```

### 3.3. Cài đặt Airflow

```bash
helm install airflow apache-airflow/airflow \
  --namespace airflow \
  --create-namespace \
  --values airflow-values.yaml
```

### 3.4. Kiểm tra

```bash
# Kiểm tra pods
kubectl get pods -n airflow

# Đợi tất cả pods Running
kubectl wait --for=condition=ready pod -l component=webserver -n airflow --timeout=300s
kubectl wait --for=condition=ready pod -l component=scheduler -n airflow --timeout=300s

# Lấy Airflow admin password
kubectl get secret airflow-webserver-secret -n airflow -o jsonpath="{.data.webserver-secret-key}" | base64 -d
```

### 3.5. Truy cập Airflow UI

```bash
# Port forward
kubectl port-forward svc/airflow-webserver 8080:8080 -n airflow

# Hoặc nếu dùng NodePort
# Truy cập: http://<node-ip>:30809
# Username: admin
# Password: (lấy từ secret)
```

## Bước 4: Deploy Spark Applications

### 4.1. Build Spark Image với code

Tạo Dockerfile cho Spark image:

```dockerfile
# Dockerfile cho Spark với code
FROM apache/spark:3.5.0

# Copy code
COPY Spark/ /opt/spark/apps/
WORKDIR /opt/spark/apps/

# Install Python dependencies
RUN pip install redis pymongo
```

Build và push image:

```bash
docker build -t spark-crypto:3.5.0 -f Dockerfile .
# Hoặc push lên registry
docker tag spark-crypto:3.5.0 your-registry/spark-crypto:3.5.0
docker push your-registry/spark-crypto:3.5.0
```

### 4.2. Deploy Spark Applications

```bash
# Cập nhật image trong spark-applications.yaml
# Sau đó apply
kubectl apply -f spark-applications.yaml
```

### 4.3. Kiểm tra Spark Applications

```bash
# Xem applications
kubectl get sparkapplications -n spark

# Xem pods
kubectl get pods -n spark

# Xem logs
kubectl logs -f <spark-driver-pod> -n spark
```

## Bước 5: Cấu hình Airflow với Spark

### 5.1. Tạo Spark Connection trong Airflow

Truy cập Airflow UI → Admin → Connections → Add:
- Connection Id: `spark_default`
- Connection Type: `Spark`
- Host: `spark-operator-service.spark.svc.cluster.local`
- Port: `8080`

### 5.2. Copy DAGs vào Airflow

```bash
# Copy DAGs
kubectl cp Spark/spark_crypto_pipeline.py \
  airflow-scheduler-0:/opt/airflow/dags/ \
  -n airflow

# Hoặc mount ConfigMap/PVC
```

### 5.3. Restart Scheduler

```bash
kubectl rollout restart deployment/airflow-scheduler -n airflow
```

## Bước 6: Deploy Redis và MongoDB (nếu chưa có)

### 6.1. Redis

```bash
helm repo add bitnami https://charts.bitnami.com/bitnami
helm install redis bitnami/redis \
  --namespace default \
  --set auth.enabled=false \
  --set persistence.enabled=true
```

### 6.2. MongoDB

```bash
helm install mongodb bitnami/mongodb \
  --namespace default \
  --set auth.enabled=false \
  --set persistence.enabled=true
```

## Troubleshooting

### Spark Operator không start

```bash
# Kiểm tra logs
kubectl logs -f deployment/spark-operator -n spark

# Kiểm tra RBAC
kubectl get clusterrole spark-operator
kubectl get clusterrolebinding spark-operator
```

### Airflow pods không start

```bash
# Kiểm tra logs
kubectl logs -f deployment/airflow-scheduler -n airflow
kubectl logs -f deployment/airflow-webserver -n airflow

# Kiểm tra PVC
kubectl get pvc -n airflow

# Kiểm tra Postgres
kubectl logs -f statefulset/airflow-postgresql -n airflow
```

### Spark Applications fail

```bash
# Xem events
kubectl describe sparkapplication crypto-redis-writer -n spark

# Xem driver logs
kubectl logs -f <driver-pod> -n spark

# Xem executor logs
kubectl logs -f <executor-pod> -n spark
```

## Upgrade

### Upgrade Spark Operator

```bash
helm upgrade spark-operator spark-operator/spark-operator \
  --namespace spark \
  --values spark-operator-values.yaml
```

### Upgrade Airflow

```bash
helm upgrade airflow apache-airflow/airflow \
  --namespace airflow \
  --values airflow-values.yaml
```

## Uninstall

```bash
# Uninstall Spark Operator
helm uninstall spark-operator -n spark

# Uninstall Airflow
helm uninstall airflow -n airflow

# Xóa namespaces
kubectl delete namespace spark
kubectl delete namespace airflow
```

## Monitoring

### Spark UI

```bash
# Port forward Spark UI
kubectl port-forward <spark-driver-pod> 4040:4040 -n spark
# Truy cập: http://localhost:4040
```

### Airflow UI

```bash
# Port forward
kubectl port-forward svc/airflow-webserver 8080:8080 -n airflow
# Truy cập: http://localhost:8080
```

## Best Practices

1. **Resource Limits**: Set resource limits cho tất cả pods
2. **Persistent Storage**: Dùng PVC cho DAGs, logs, checkpoints
3. **Backup**: Backup Airflow database và DAGs
4. **Monitoring**: Setup Prometheus và Grafana
5. **Security**: Enable authentication cho Airflow
6. **Scaling**: Scale workers dựa trên workload

