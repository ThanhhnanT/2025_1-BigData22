# Hướng dẫn triển khai hệ thống (reproduce.md)

Tài liệu này mô tả cách triển khai toàn bộ hệ thống CRYPTO (Kafka + Spark ML + Airflow + Backend FastAPI + Frontend Next.js + Monitoring) trên **minikube**.

> Lưu ý: Hướng dẫn dùng cho môi trường local dev trên minikube, chạy trên Windows nên khuyến nghị dùng **WSL2** hoặc Linux shell để chạy các script `.sh`.

---

## 1. Chuẩn bị môi trường

### 1.1. Cài đặt bắt buộc

- Docker (Docker Desktop hoặc Docker Engine)
- kubectl
- minikube
- helm (v3 trở lên)
- Git
- Python 3.10+ (nếu muốn chạy script lẻ bên ngoài K8s)

Kiểm tra nhanh:

```bash
kubectl version --client
minikube version
helm version
```

### 1.2. Khởi động minikube

```bash
minikube start --cpus=4 --memory=8192

# Khuyến nghị bật ingress addon (nếu chưa bật)
minikube addons enable ingress
```

---

## 2. Clone project & cấu trúc chính

```bash
git clone <repo-url>
cd 2025_1-BigData22
```

Các thư mục chính:
- `Kafka/`: Producer Binance → Kafka + consumer Redis/Mongo
- `Spark/`: Batch & ML (train/predict) trên Spark + Spark Operator
- `airflow/`: Airflow DAGs orchestration cho SparkApplication
- `backend_fastapi/`: REST & WebSocket API
- `frontend/`: Next.js dashboard
- `deploy/k8s_web/`: Manifest K8s cho backend/frontend/ingress
- `deploy/helm/`: Script & values triển khai Prometheus + Grafana

---

## 3. Dựng hạ tầng cơ bản (Kafka, Mongo, Redis, Spark Operator)

Phần này phụ thuộc vào cách bạn muốn dựng stack. Repo đã chuẩn bị Helm chart cho các thành phần chính.

### 3.1. Tạo namespace chính

```bash
# Namespace cho ứng dụng web (backend + frontend)
kubectl apply -f deploy/k8s_web/namespace.yaml

# Namespace cho infra (Kafka, Spark, Airflow, v.v.)
# Tùy repo của bạn, thường là "crypto-infra"; nếu có manifest sẵn thì áp dụng tương tự.
```

### 3.2. Cài Kafka bằng Strimzi (tham khảo thư mục Kafka/)

```bash
cd Kafka/strimzi-kafka-operator
# Cài CRDs + Operator (ví dụ)
kubectl create namespace crypto-infra || true
kubectl apply -f install/cluster-operator/

# Áp dụng cấu hình cluster Kafka (ví dụ)
cd ..
kubectl apply -f kafka-helm.yaml -n crypto-infra
```

Đảm bảo pod Kafka broker và Zookeeper đã chạy:

```bash
kubectl get pods -n crypto-infra
```

### 3.3. Cài MongoDB & Redis bằng Helm (nếu chưa có)

Bạn có thể dùng chart riêng hoặc chart chính thức:

```bash
# Ví dụ: sử dụng bitnami (tuỳ chọn, có thể thay bằng chart nội bộ nếu đã cấu hình sẵn)
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo update

# MongoDB
helm install crypto-mongo bitnami/mongodb \
  --namespace crypto-infra --create-namespace \
  --set auth.rootPassword=changeme

# Redis
helm install crypto-redis bitnami/redis \
  --namespace crypto-infra --create-namespace \
  --set auth.password=changeme
```

Sau đó cập nhật lại `deploy/k8s_web/configmap.yaml` và `secret.yaml` cho đúng URI kết nối (Mongo/Redis/Kafka).

### 3.4. Cài Spark Operator (Spark on Kubernetes)

```bash
# Ví dụ: dùng Helm chart chính thức của spark-operator
helm repo add spark-operator https://googlecloudplatform.github.io/spark-on-k8s-operator
helm repo update

helm install spark-operator spark-operator/spark-operator \
  --namespace spark-operator --create-namespace \
  --set sparkJobNamespace=crypto-infra \
  --set webhook.enable=true
```

SparkApplication manifests (train-price-prediction.yaml, predict-price.yaml) sẽ chạy trong namespace `crypto-infra`.

---

## 4. Triển khai Monitoring (Prometheus + Grafana)

Repo đã chuẩn bị script tự động trong `deploy/helm/`.

### 4.1. Cài monitoring stack

```bash
cd deploy/helm
./deploy-monitoring.sh
```

Script này sẽ:
- Tạo namespace `crypto-monitoring`
- Cài `kube-prometheus-stack` với cấu hình từ `values-minikube.yaml`

### 4.2. Áp dụng ServiceMonitor cho các service

```bash
cd ../k8s_web/monitoring
./apply-servicemonitors.sh
```

### 4.3. Truy cập Grafana & Prometheus

```bash
# Grafana (NodePort hoặc port-forward)
minikube service crypto-monitoring-grafana -n crypto-monitoring
# hoặc
kubectl port-forward svc/crypto-monitoring-grafana 3000:80 -n crypto-monitoring

# Prometheus
kubectl port-forward svc/crypto-monitoring-kube-prometheus-prometheus 9090:9090 -n crypto-monitoring
```

---

## 5. Build & deploy Backend + Frontend

Repo đã có script tiện dụng cho minikube: `deploy/k8s_web/build-and-deploy.sh`.

### 5.1. Chạy build & deploy tự động

```bash
cd deploy/k8s_web
chmod +x build-and-deploy.sh
./build-and-deploy.sh     # deploy cả backend & frontend + ingress

# Hoặc chỉ backend
./build-and-deploy.sh --backend

# Hoặc chỉ frontend
./build-and-deploy.sh --frontend
```

Script sẽ:
- Dùng Docker daemon của minikube (`eval $(minikube docker-env)`) để build image:
  - Backend: `crypto-backend-fastapi:latest`
  - Frontend: `crypto-frontend-next:local`
- Áp dụng các manifest:
  - `configmap.yaml`, `secret.yaml`
  - `backend-deployment.yaml`, `backend-service.yaml`
  - `frontend-deployment.yaml`, `frontend-service.yaml`
  - `ingress.yaml`

### 5.2. Kiểm tra trạng thái

```bash
kubectl get pods -n crypto-app
kubectl get svc -n crypto-app
kubectl get ingress -n crypto-app
```

### 5.3. Truy cập ứng dụng

Script sẽ tự in gợi ý, nhưng cơ bản:

- Truy cập trực tiếp qua port-forward:

```bash
# Backend API
kubectl port-forward svc/backend-fastapi-service 8000:8000 -n crypto-app
# → http://localhost:8000

# Frontend
kubectl port-forward svc/frontend-next-service 3000:3000 -n crypto-app
# → http://localhost:3000
```

- Truy cập qua Ingress:

```bash
INGRESS_IP=$(minikube ip)
# Thêm vào /etc/hosts (trên WSL/Linux)
echo "${INGRESS_IP} crypto.local" | sudo tee -a /etc/hosts

# Sau đó mở:
# Frontend: http://crypto.local
# Backend API: http://crypto.local/api
```

---

## 6. Chạy luồng dữ liệu & ML Pipeline

### 6.1. Khởi động Kafka Producer từ Binance

Triển khai container từ Dockerfile trong `Kafka/` hoặc chạy local:

```bash
cd Kafka
# (Tuỳ bạn build image và tạo Deployment/Job cho producer)
# Local test:
python binance_producer.py
```

Producer sẽ stream kline 1m từ Binance vào Kafka topic `crypto_kline_1m`.

### 6.2. Consumer → Redis/Mongo

Tương tự, triển khai các consumer:

```bash
cd Kafka
python redis_consumer.py
python redis_orderbook_trades_consumer.py
```

Trong môi trường K8s, nên đóng gói các script này thành image và tạo Deployment/Job riêng để chúng chạy trong cluster.

### 6.3. Airflow orchestration (train/predict)

Airflow trong repo dùng để submit SparkApplication trên K8s:

- DAGs: `airflow/dags/ml_prediction_dag.py`
  - `crypto_ml_training` (chạy 2h sáng hàng ngày)
  - `crypto_ml_prediction` (mỗi phút)

Bạn có thể:
- Deploy Airflow (ví dụ bằng Helm chart chính thức hoặc chart trong thư mục `airflow/`).
- Mount thư mục DAGs repo vào Airflow (`ml_prediction_dag.py`).
- Đảm bảo Airflow có quyền `kubectl` vào namespace `crypto-infra` (xem `airflow-worker-clusterrole.yaml`).

Sau khi Airflow chạy:
- Bật DAG `crypto_ml_training` để train model lần đầu.
- Bật DAG `crypto_ml_prediction` để chạy prediction định kỳ.

### 6.4. Kiểm tra dữ liệu & prediction

- MongoDB:
  - Lịch sử giá (kline) + predictions lưu trong DB (ví dụ DB `CRYPTO`).
- Redis:
  - Keys OHLC realtime: `crypto:{SYMBOL}:1m:*`
  - Keys predictions: `crypto:prediction:{SYMBOL}`.

Backend FastAPI sẽ đọc từ Redis/Mongo để trả về:
- `GET /ohlc`, `/ohlc/realtime`, `/orderbook`, `/trades`
- `GET /predictions`, `/prediction/{symbol}`, `/prediction/{symbol}/history`

Frontend sẽ hiển thị chart / orderbook / dự đoán realtime.

---

## 7. Kiểm tra end-to-end

1. Đảm bảo:
   - Kafka, Redis, Mongo, Spark Operator, Airflow, backend, frontend đều đang `Running`.
2. Mở Grafana để xem metrics và dashboards.
3. Mở frontend (http://crypto.local hoặc http://localhost:3000) xem:
   - Biểu đồ giá realtime cập nhật.
   - Order book & trades.
   - Tín hiệu prediction (UP/DOWN, % change).

Nếu tất cả các bước trên hoạt động, bạn đã reproduce thành công toàn bộ hệ thống CRYPTO trên minikube.
