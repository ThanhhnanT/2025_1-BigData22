# Báo cáo Trạng thái Monitoring

## Tổng quan

Báo cáo này liệt kê tất cả các components trong hệ thống và trạng thái kết nối với Prometheus/Grafana.

## ✅ Đã có ServiceMonitor (Đã kết nối)

### 1. Backend FastAPI
- **ServiceMonitor**: `backend-servicemonitor.yaml`
- **Namespace**: `crypto-app`
- **Port**: `http` (8000)
- **Metrics Path**: `/metrics`
- **Status**: ✅ Đã kết nối
- **Yêu cầu**: Backend phải có Prometheus client library (prometheus-fastapi-instrumentator)

### 2. Kafka (Strimzi)
- **ServiceMonitor**: `kafka-servicemonitor.yaml`
- **Namespace**: `crypto-infra`
- **Port**: `tcp-prometheus`
- **Metrics Path**: `/metrics`
- **Status**: ✅ Đã kết nối
- **Yêu cầu**: Kafka cluster phải có metrics config enabled

### 3. Spark Operator
- **ServiceMonitor**: `spark-operator-servicemonitor.yaml`
- **Namespace**: `crypto-infra`
- **Port**: `metrics`
- **Metrics Path**: `/metrics`
- **Status**: ✅ Đã kết nối

### 4. Airflow StatsD
- **ServiceMonitor**: `airflow-statsd-servicemonitor.yaml`
- **Namespace**: `crypto-infra`
- **Port**: `statsd-scrape`
- **Metrics Path**: `/metrics`
- **Status**: ✅ Đã kết nối
- **Yêu cầu**: Airflow phải có statsd enabled

## ⚠️ Cần bật Metrics trước (ServiceMonitor đã sẵn sàng)

### 5. MongoDB
- **ServiceMonitor**: `mongodb-servicemonitor.yaml` ✅ Đã tạo
- **Namespace**: `crypto-infra`
- **Port**: `http-metrics`
- **Status**: ⚠️ Cần enable metrics trong Helm chart
- **Cách bật**:
  ```yaml
  # Trong values.yaml của MongoDB Helm chart
  metrics:
    enabled: true
  serviceMonitor:
    enabled: true
    namespace: crypto-infra
    labels:
      release: crypto-monitoring
  ```

### 6. Redis
- **ServiceMonitor**: `redis-servicemonitor.yaml` ✅ Đã tạo
- **Namespace**: `crypto-infra`
- **Port**: `http-metrics`
- **Status**: ⚠️ Cần enable metrics trong Helm chart
- **Cách bật**:
  ```yaml
  # Trong values.yaml của Redis Helm chart
  metrics:
    enabled: true
  serviceMonitor:
    enabled: true
    namespace: crypto-infra
    labels:
      release: crypto-monitoring
  ```

## ❌ Chưa có Monitoring

### 7. Frontend (Next.js)
- **Status**: ❌ Chưa có metrics endpoint
- **Lý do**: Next.js không tự động expose Prometheus metrics
- **Giải pháp đề xuất**:
  1. Cài đặt `prom-client` package
  2. Tạo API route `/api/metrics` để expose metrics
  3. Tạo ServiceMonitor cho frontend service
  4. **Hoặc**: Chỉ monitor qua Kubernetes metrics (CPU, Memory, Pod status)

### 8. Kafka Producers/Consumers
- **Components**:
  - `binance-producer`
  - `redis-consumer`
  - `binance-orderbook-producer`
- **Status**: ❌ Chưa có metrics
- **Giải pháp đề xuất**:
  1. Thêm Prometheus client library vào Python apps
  2. Expose metrics endpoint trên port riêng (ví dụ: 9090)
  3. Tạo Service cho metrics endpoint
  4. Tạo ServiceMonitor cho từng component

### 9. Spark Applications
- **Status**: ⚠️ Có thể monitor qua Spark UI nhưng chưa tích hợp Prometheus
- **Giải pháp đề xuất**:
  1. Sử dụng Spark metrics system
  2. Expose metrics qua JMX hoặc HTTP endpoint
  3. Sử dụng Spark Prometheus sink
  4. Tạo ServiceMonitor cho Spark driver pods

## 📋 Checklist để hoàn thiện Monitoring

### Bước 1: Bật Metrics cho MongoDB và Redis
```bash
# Cập nhật Helm values cho MongoDB
# Cập nhật Helm values cho Redis
# Upgrade Helm releases
helm upgrade <mongodb-release> <mongodb-chart> -f values.yaml -n crypto-infra
helm upgrade <redis-release> <redis-chart> -f values.yaml -n crypto-infra
```

### Bước 2: Áp dụng ServiceMonitors
```bash
cd deploy/monitoring
./apply-servicemonitors.sh
```

### Bước 3: Verify trong Prometheus
```bash
kubectl port-forward svc/crypto-monitoring-kube-prometheus-prometheus 9090:9090 -n crypto-monitoring
# Mở http://localhost:9090/targets để kiểm tra
```

### Bước 4: (Tùy chọn) Thêm Metrics cho Frontend
- Cài đặt `prom-client` trong frontend
- Tạo `/api/metrics` endpoint
- Tạo ServiceMonitor cho frontend

### Bước 5: (Tùy chọn) Thêm Metrics cho Kafka Apps
- Thêm `prometheus-client` vào Python apps
- Expose metrics endpoint
- Tạo Service và ServiceMonitor

## 📊 Tổng kết

| Component | ServiceMonitor | Metrics Enabled | Status |
|-----------|---------------|-----------------|--------|
| Backend FastAPI | ✅ | ✅ | ✅ Hoàn thành |
| Kafka | ✅ | ✅ | ✅ Hoàn thành |
| Spark Operator | ✅ | ✅ | ✅ Hoàn thành |
| Airflow StatsD | ✅ | ✅ | ✅ Hoàn thành |
| MongoDB | ✅ | ❌ | ⚠️ Cần bật metrics |
| Redis | ✅ | ❌ | ⚠️ Cần bật metrics |
| Frontend | ❌ | ❌ | ❌ Chưa có |
| Kafka Producers | ❌ | ❌ | ❌ Chưa có |
| Kafka Consumers | ❌ | ❌ | ❌ Chưa có |
| Spark Apps | ❌ | ❌ | ❌ Chưa có |

## 🔗 Tài liệu tham khảo

- [Prometheus Operator Documentation](https://github.com/prometheus-operator/prometheus-operator)
- [MongoDB Metrics Exporter](https://github.com/percona/mongodb_exporter)
- [Redis Metrics Exporter](https://github.com/oliver006/redis_exporter)
- [Prometheus Client for Python](https://github.com/prometheus/client_python)
- [Prometheus Client for Node.js](https://github.com/siimon/prom-client)

