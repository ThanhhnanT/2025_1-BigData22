# Hướng dẫn Query Metrics cho Services hiện tại

## Services đang chạy trong crypto-infra

### 1. Airflow
- **Pods**: airflow-api-server, airflow-scheduler, airflow-worker, airflow-statsd
- **Service**: `airflow-statsd` (port 9102/TCP cho metrics)

### 2. Kafka (Strimzi)
- **Pods**: my-cluster-dual-role-0/1/2
- **Services**: my-cluster-kafka-bootstrap, my-cluster-kafka-brokers

### 3. Spark Operator
- **Pods**: spark-kubernetes-operator-xxx (3 replicas)

### 4. Redis
- **Pods**: my-redis-master-0, my-redis-replicas-0/1/2

### 5. MongoDB
- **Pods**: my-mongo-mongodb-xxx

---

## Query Metrics trong Grafana

### Bước 1: Vào Grafana Explore
1. Mở Grafana: http://<minikube-ip>:30002
2. Login: admin / 12345678
3. Click **Explore** (biểu tượng compass)

### Bước 2: Chọn Prometheus Data Source

---

## Query Examples

### 1. Kiểm tra tất cả targets đang scrape
```promql
up
```

### 2. Xem metrics từ namespace crypto-infra
```promql
{namespace="crypto-infra"}
```

### 3. Airflow Metrics

#### Airflow Pods CPU Usage
```promql
sum(rate(container_cpu_usage_seconds_total{namespace="crypto-infra", pod=~"airflow.*"}[5m])) by (pod)
```

#### Airflow Pods Memory Usage
```promql
sum(container_memory_working_set_bytes{namespace="crypto-infra", pod=~"airflow.*"}) by (pod)
```

#### Airflow StatsD Metrics (nếu có)
```promql
{__name__=~".*airflow.*", namespace="crypto-infra"}
```

### 4. Kafka Metrics

#### Kafka Pods CPU Usage
```promql
sum(rate(container_cpu_usage_seconds_total{namespace="crypto-infra", pod=~"my-cluster.*"}[5m])) by (pod)
```

#### Kafka Pods Memory Usage
```promql
sum(container_memory_working_set_bytes{namespace="crypto-infra", pod=~"my-cluster.*"}) by (pod)
```

#### Kafka Metrics (nếu đã cấu hình JMX)
```promql
{__name__=~"kafka_server_.*", namespace="crypto-infra"}
```

### 5. Spark Operator Metrics

#### Spark Operator Pods CPU
```promql
sum(rate(container_cpu_usage_seconds_total{namespace="crypto-infra", pod=~"spark-kubernetes-operator.*"}[5m])) by (pod)
```

#### Spark Operator Pods Memory
```promql
sum(container_memory_working_set_bytes{namespace="crypto-infra", pod=~"spark-kubernetes-operator.*"}) by (pod)
```

### 6. Redis Metrics

#### Redis Pods CPU
```promql
sum(rate(container_cpu_usage_seconds_total{namespace="crypto-infra", pod=~"my-redis.*"}[5m])) by (pod)
```

#### Redis Pods Memory
```promql
sum(container_memory_working_set_bytes{namespace="crypto-infra", pod=~"my-redis.*"}) by (pod)
```

### 7. MongoDB Metrics

#### MongoDB Pod CPU
```promql
sum(rate(container_cpu_usage_seconds_total{namespace="crypto-infra", pod=~"my-mongo.*"}[5m])) by (pod)
```

#### MongoDB Pod Memory
```promql
sum(container_memory_working_set_bytes{namespace="crypto-infra", pod=~"my-mongo.*"}) by (pod)
```

### 8. Binance Producer/Consumer Metrics

#### Binance Pods CPU
```promql
sum(rate(container_cpu_usage_seconds_total{namespace="crypto-infra", pod=~"binance.*"}[5m])) by (pod)
```

#### Binance Pods Memory
```promql
sum(container_memory_working_set_bytes{namespace="crypto-infra", pod=~"binance.*"}) by (pod)
```

---

## Query Patterns Hữu Ích

### Tìm tất cả metrics từ một pod cụ thể
```promql
{pod="airflow-scheduler-d9d5bdf8c-dvxfh", namespace="crypto-infra"}
```

### Tìm metrics từ một service
```promql
{service="airflow-statsd", namespace="crypto-infra"}
```

### CPU usage của tất cả pods trong namespace
```promql
sum(rate(container_cpu_usage_seconds_total{namespace="crypto-infra", container!="POD", container!=""}[5m])) by (pod)
```

### Memory usage của tất cả pods
```promql
sum(container_memory_working_set_bytes{namespace="crypto-infra", container!="POD", container!=""}) by (pod)
```

### Top 10 pods sử dụng CPU nhiều nhất
```promql
topk(10, sum(rate(container_cpu_usage_seconds_total{namespace="crypto-infra", container!="POD"}[5m])) by (pod))
```

### Top 10 pods sử dụng Memory nhiều nhất
```promql
topk(10, sum(container_memory_working_set_bytes{namespace="crypto-infra", container!="POD"}) by (pod))
```

---

## Kiểm tra Metrics Endpoints

### Test Airflow StatsD
```bash
kubectl port-forward svc/airflow-statsd 9102:9102 -n crypto-infra
curl http://localhost:9102/metrics
```

### Test Kafka Metrics (nếu có)
```bash
# Lấy tên pod Kafka
KAFKA_POD=$(kubectl get pods -n crypto-infra | grep my-cluster-dual-role | head -1 | awk '{print $1}')

# Port forward (nếu có metrics port 9404)
kubectl port-forward $KAFKA_POD 9404:9404 -n crypto-infra
curl http://localhost:9404/metrics
```

---

## Tạo Dashboard

### Dashboard cho tất cả services

1. **Vào Dashboards** → **New** → **New Dashboard**
2. **Add visualization**
3. **Chọn Prometheus data source**

#### Panel 1: CPU Usage của tất cả pods
```promql
sum(rate(container_cpu_usage_seconds_total{namespace="crypto-infra", container!="POD"}[5m])) by (pod)
```
- Visualization: **Time series**
- Unit: **percent (0-100)**

#### Panel 2: Memory Usage của tất cả pods
```promql
sum(container_memory_working_set_bytes{namespace="crypto-infra", container!="POD"}) by (pod)
```
- Visualization: **Time series**
- Unit: **bytes (IEC)**

#### Panel 3: Pod Status
```promql
kube_pod_status_phase{namespace="crypto-infra"}
```
- Visualization: **Stat**
- Value options: **Last**

#### Panel 4: Restart Count
```promql
kube_pod_container_status_restarts_total{namespace="crypto-infra"}
```
- Visualization: **Time series**

---

## Quick Reference

### Tìm metrics có chứa từ khóa
```promql
{__name__=~".*kafka.*"}
{__name__=~".*airflow.*"}
{__name__=~".*spark.*"}
{__name__=~".*redis.*"}
{__name__=~".*mongo.*"}
```

### Filter theo label
```promql
{namespace="crypto-infra", app="airflow"}
{namespace="crypto-infra", component="scheduler"}
```

### Tính tổng/trung bình
```promql
sum(metric_name) by (pod)
avg(metric_name) by (namespace)
```

### Rate (tốc độ thay đổi)
```promql
rate(metric_name[5m])
```

---

## Troubleshooting

### Không thấy metrics?

1. **Kiểm tra Prometheus targets:**
   ```bash
   kubectl port-forward svc/crypto-monitoring-kube-pro-prometheus 9090:9090 -n crypto-monitoring
   # Mở: http://localhost:9090/targets
   ```

2. **Kiểm tra pod labels:**
   ```bash
   kubectl get pod <pod-name> -n crypto-infra --show-labels
   ```

3. **Kiểm tra service có expose metrics:**
   ```bash
   kubectl get svc <service-name> -n crypto-infra -o yaml | grep -A 5 ports
   ```

4. **Test metrics endpoint trực tiếp:**
   ```bash
   kubectl port-forward svc/<service-name> <port> -n crypto-infra
   curl http://localhost:<port>/metrics
   ```

