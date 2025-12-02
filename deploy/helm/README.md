### Mục tiêu

- **Triển khai toàn bộ pipeline CRYPTO trên minikube bằng Helm**, sử dụng:
  - **Strimzi Kafka Operator** (`strimzi-kafka-operator` chart) + Kafka CR trong `Kafka/kafka-helm.yaml`.
  - Chart Spark Operator local trong `Spark/spark-kubernetes-operator/`.
  - Chart Airflow local trong `airflow/airflow/`.
  - Chart monitoring `kube-prometheus-stack` từ `prometheus-community`.
- Tất cả cấu hình môi trường **được gom trong** `deploy/helm/values-minikube.yaml` để sau này dễ mở rộng sang AWS (tạo thêm `values-aws.yaml`).

Thiết kế này tương tự cách tổ chức trong repo tham chiếu [`End-to-End-Data-Pipeline`](https://github.com/hoangsonww/End-to-End-Data-Pipeline).

---

### Cấu trúc

```text
deploy/
  helm/
    README.md
    values-minikube.yaml
    create-dags-configmap.sh
```

- `values-minikube.yaml`: chứa các block cấu hình:
  - `global`, `namespaces`
  - `kafka` – cấu hình cho release Kafka.
  - `sparkOperator` – cấu hình cho Spark Operator.
  - `airflow` – cấu hình cho Airflow (bao gồm mount DAGs từ ConfigMap).
  - `monitoring` – cấu hình cho Prometheus + Grafana.
- `create-dags-configmap.sh`: script để tạo/update Kubernetes ConfigMap từ DAG files trong `airflow/dags/`.

---

### Chuẩn bị minikube

```bash
minikube start \
  --cpus=4 \
  --memory=8192 \
  --driver=docker

kubectl create namespace crypto-infra
kubectl create namespace crypto-monitoring
```

Tùy máy, bạn có thể giảm `cpus`/`memory`, nhưng nên >= 4 CPU và 8 GB RAM cho Kafka + Spark + Airflow + monitoring.

---

### Thêm Helm repositories bên ngoài

```bash
helm repo add strimzi https://strimzi.io/charts/
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update
```

- Kafka: dùng **Strimzi** (`strimzi/strimzi-kafka-operator`), còn cluster Kafka được định nghĩa bằng CR trong `Kafka/kafka-helm.yaml`.
- Monitoring: dùng chart `prometheus-community/kube-prometheus-stack`.

---

### 1. Cài Strimzi Kafka Operator + Kafka cluster

#### 1.1. Cài Strimzi Kafka Operator

```bash
helm install strimzi-kafka-operator strimzi/strimzi-kafka-operator \
  --namespace crypto-infra \
  -f deploy/helm/values-minikube.yaml
```

- Release name: `strimzi-kafka-operator`.
- Namespace: `crypto-infra`.
- Cấu hình chi tiết đọc từ block `kafka` trong `values-minikube.yaml`.

#### 1.2. Tạo Kafka cluster bằng CR của Strimzi

Sau khi operator chạy, apply manifest Kafka của bạn (đã có trong dự án):

```bash
kubectl apply -f Kafka/kafka-helm.yaml -n crypto-infra
```

- File này chứa `KafkaNodePool` và `Kafka` (`apiVersion: kafka.strimzi.io/v1beta2`), ví dụ:

```23:53:Kafka/kafka-helm.yaml
apiVersion: kafka.strimzi.io/v1beta2
kind: Kafka
metadata:
  name: my-cluster
  annotations:
    strimzi.io/node-pools: enabled
    strimzi.io/kraft: enabled
spec:
  kafka:
    listeners:
      - name: plain
        port: 9092
        type: internal
        tls: false
      - name: tls
        port: 9093
        type: internal
        tls: true
      - name: external
        port: 9094
        type: nodeport
        tls: false
  entityOperator:
    topicOperator: {}
    userOperator: {}
```

- Sau bước này, bạn có một Kafka cluster Strimzi (`my-cluster`) chạy trong namespace `crypto-infra`.

---

### 2. Cài Spark Operator

```bash
helm install crypto-spark-operator ./Spark/spark-kubernetes-operator \
  --namespace crypto-infra \
  -f deploy/helm/values-minikube.yaml
```

- Release name: `crypto-spark-operator`.
- Namespace: `crypto-infra`.
- Block `sparkOperator` trong `values-minikube.yaml`:
  - Tạo `ServiceAccount` cho operator.
  - Đặt `sparkJobNamespace: crypto-infra`.
  - Bật metrics Prometheus cho operator để monitoring stack có thể scrape được.

Sau khi Spark Operator chạy, bạn có thể apply các `SparkApplication` (ví dụ file `Spark/spark-helm.yaml` hoặc các manifest khác) để chạy job batch/streaming.

---

### 3. Cài Airflow

**Lần đầu cài:**

```bash
helm install crypto-airflow ./airflow/airflow \
  --namespace crypto-infra \
  -f deploy/helm/values-minikube.yaml
```

**Upgrade Airflow (khi thay đổi cấu hình hoặc image):**

Nếu gặp lỗi về StatefulSet không thể update, có 2 cách:

**Cách 1: Xóa và cài lại (mất dữ liệu, OK cho dev):**

```bash
# Xóa release
helm uninstall crypto-airflow -n crypto-infra

# Xóa StatefulSet nếu còn tồn tại
kubectl delete statefulset crypto-airflow-postgresql -n crypto-infra --ignore-not-found=true

# Cài lại
helm install crypto-airflow ./airflow/airflow \
  --namespace crypto-infra \
  -f deploy/helm/values-minikube.yaml
```

Hoặc dùng script tự động:

```bash
cd deploy/helm
./fix-airflow-upgrade.sh crypto-infra
```

**Cách 2: Giữ dữ liệu (chỉ xóa StatefulSet, giữ PVC):**

```bash
# Xóa StatefulSet nhưng giữ PVC
kubectl delete statefulset crypto-airflow-postgresql -n crypto-infra --cascade=orphan

# Upgrade lại
helm upgrade crypto-airflow ./airflow/airflow \
  --namespace crypto-infra \
  -f deploy/helm/values-minikube.yaml
```

- Release name: `crypto-airflow`.
- Namespace: `crypto-infra`.
- Block `airflow` trong `values-minikube.yaml` hiện cấu hình:
  - `executor: CeleryExecutor`.
  - `webserver.service.type: NodePort` để dễ truy cập từ minikube (với Airflow 3.0+, service có thể là `api-server`).
  - Tắt persistence logs/DAGs cho đơn giản khi dev local.
  - Mount DAGs từ ConfigMap `crypto-airflow-dags` vào tất cả components.
  - Bật `statsd.enabled: true` để có thể xuất metrics sang Prometheus thông qua exporter (matching với cách repo tham chiếu dùng  Airflow + monitoring).

Truy cập Airflow Web UI:

```bash
# Với Airflow 3.0+, sử dụng api-server thay vì webserver
kubectl port-forward svc/crypto-airflow-api-server 8080:8080 -n crypto-infra
```

Sau đó mở `http://localhost:8080`.

**Lưu ý:** Với Airflow 3.0+, service name là `crypto-airflow-api-server` thay vì `crypto-airflow-webserver`. Nếu bạn thấy service `crypto-airflow-webserver` trong cluster, có thể dùng service đó thay thế.

#### 3.1. Cấu hình DAGs cho Airflow

Airflow cần DAG files để chạy các workflow. Có 2 cách để đưa DAGs vào Airflow:

##### Cách 1: Custom Dockerfile (Khuyến nghị)

DAGs được bake vào Docker image, không cần mount. Cách này phù hợp cho production và CI/CD.

**Build custom Airflow image:**

Có 2 cách:

**Cách 1: Build local và load vào minikube (cho dev):**

```bash
cd airflow
docker build -t crypto-airflow:latest -f Dockerfile .
minikube image load crypto-airflow:latest
```

**Cách 2: Build và push lên Docker Hub (cho production):**

```bash
cd airflow

# Login vào Docker Hub (nếu chưa login)
docker login

# Build và push (thay YOUR_USERNAME bằng Docker Hub username của bạn)
./build-and-push.sh YOUR_USERNAME latest

# Hoặc với tag cụ thể
./build-and-push.sh YOUR_USERNAME v1.0.0
```

Sau đó cập nhật `deploy/helm/values-minikube.yaml`:

```yaml
images:
  airflow:
    repository: YOUR_USERNAME/crypto-airflow
    tag: latest
    pullPolicy: Always  # Hoặc IfNotPresent
```

**Cài Airflow với custom image:**

Image đã được cấu hình trong `values-minikube.yaml`:
- `images.airflow.repository: crypto-airflow`
- `images.airflow.tag: latest`

Chỉ cần cài Airflow như bình thường:

```bash
helm install crypto-airflow ./airflow/airflow \
  --namespace crypto-infra \
  -f deploy/helm/values-minikube.yaml
```

**Cập nhật DAGs sau khi thay đổi:**

1. Rebuild image:
   ```bash
   cd airflow
   docker build -t crypto-airflow:latest -f Dockerfile .
   minikube image load crypto-airflow:latest
   ```

2. Upgrade Helm release:
   ```bash
   helm upgrade crypto-airflow ./airflow/airflow \
     --namespace crypto-infra \
     -f deploy/helm/values-minikube.yaml
   ```

3. Restart pods để pull image mới:
   ```bash
   kubectl rollout restart deployment crypto-airflow-scheduler -n crypto-infra
   kubectl rollout restart deployment crypto-airflow-api-server -n crypto-infra
   kubectl rollout restart statefulset crypto-airflow-worker -n crypto-infra
   kubectl rollout restart deployment crypto-airflow-dag-processor -n crypto-infra
   ```

**Ưu điểm:**
- DAGs được bake vào image, không cần mount
- Không bị giới hạn kích thước ConfigMap (1MB)
- Dễ quản lý và deploy
- Phù hợp với CI/CD pipeline

##### Cách 2: ConfigMap (Alternative)

Nếu muốn dùng ConfigMap thay vì Dockerfile, xem script `deploy/helm/create-dags-configmap.sh` và cấu hình mount trong `values-minikube.yaml`.

**Lưu ý:**
- ConfigMap có giới hạn kích thước (thường là 1MB)
- Cần restart pods sau mỗi lần update ConfigMap
- Để dùng GitSync, cấu hình `dags.gitSync.enabled: true` trong `values-minikube.yaml`

---

### 4. Cài Monitoring (Prometheus + Grafana)

```bash
helm install crypto-monitoring prometheus/kube-prometheus-stack \
  --namespace crypto-monitoring \
  -f deploy/helm/values-minikube.yaml
```

- Release name: `crypto-monitoring`.
- Namespace: `crypto-monitoring`.
- Block `monitoring` trong `values-minikube.yaml`:
  - `grafana.service.type: NodePort` để truy cập qua minikube.
  - Gợi ý cấu trúc `prometheus.prometheusSpec.additionalScrapeConfigs` để scrape thêm:
    - Kafka (từ service của chart Kafka).
    - Spark Operator (metrics endpoint trên port 10254).
    - Airflow statsd/exporter.

Truy cập Grafana:

```bash
kubectl port-forward svc/crypto-monitoring-grafana 3000:80 -n crypto-monitoring
```

Sau đó mở `http://localhost:3000` và đăng nhập bằng tài khoản mặc định (thường là `admin/admin` – kiểm tra lại theo version chart).

---

### 5. Kết nối các thành phần với monitoring

- **Kafka**
  - Bật metrics trong chart Kafka theo README của chart (Bitnami hoặc chart bạn dùng).
  - Đảm bảo Prometheus có job scrape tới service Kafka (ví dụ thông qua `prometheusSpec.additionalScrapeConfigs`).
- **Spark Operator & Spark jobs**
  - `sparkOperator.values.metrics` đã bật trong `values-minikube.yaml`, operator sẽ expose metrics cho Prometheus.
  - Với từng `SparkApplication`, bạn có thể thêm cấu hình Prometheus sink nếu cần metrics chi tiết cho job.
- **Airflow**
  - `statsd.enabled: true` trong block `airflow` để phát metrics.
  - Thêm Airflow exporter hoặc metrics integration theo hướng dẫn chart để Prometheus có thể scrape.

Thiết kế này bám theo mô hình trong [`End-to-End-Data-Pipeline`](https://github.com/hoangsonww/End-to-End-Data-Pipeline), nơi Prometheus & Grafana giám sát toàn bộ luồng Kafka → Spark → Airflow.

---

### 6. Gợi ý mở rộng sang AWS/Terraform

- Tạo thêm file `deploy/helm/values-aws.yaml` để:
  - Bật `persistence.enabled: true` cho Kafka, Airflow, Prometheus/Grafana.
  - Đổi `storageClass` sang loại của EKS (hoặc cloud provider khác).
  - Đổi `service.type` sang `LoadBalancer` hoặc dùng Ingress controller.
- Trong Terraform, bạn có thể:
  - Tạo EKS cluster.
  - Dùng `helm_release` (Terraform Helm provider) để apply cùng các chart với `values-aws.yaml`.

Nhờ việc gom cấu hình vào `values-minikube.yaml` (và sau này `values-aws.yaml`), kiến trúc pipeline của bạn sẽ tương đồng với repo `End-to-End-Data-Pipeline` nhưng tối ưu cho use case crypto và dễ mang lên cloud.


