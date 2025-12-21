# Hướng dẫn Tạo Grafana Dashboard cho Hệ thống Crypto

Tài liệu này cung cấp các câu truy vấn PromQL để tạo dashboard Grafana cho hệ thống monitoring hiện tại.

## Mục lục

1. [Dashboard Tổng quan Hệ thống](#dashboard-tổng-quan-hệ-thống)
2. [Dashboard Backend FastAPI](#dashboard-backend-fastapi)
3. [Dashboard Kafka](#dashboard-kafka)
4. [Dashboard Airflow](#dashboard-airflow)
5. [Dashboard Spark Operator](#dashboard-spark-operator)
6. [Dashboard MongoDB](#dashboard-mongodb)
7. [Dashboard Redis](#dashboard-redis)
8. [Dashboard Kubernetes Resources](#dashboard-kubernetes-resources)
9. [Dashboard Network & Traffic](#dashboard-network--traffic)

---

## Dashboard Tổng quan Hệ thống

### Panel 1: Tổng số Pods theo Namespace
```promql
count(kube_pod_info{namespace=~"crypto-.*"}) by (namespace)
```
- **Visualization**: Stat
- **Unit**: short
- **Title**: Total Pods by Namespace

### Panel 2: Pods Status Overview
```promql
sum(kube_pod_status_phase{namespace=~"crypto-.*"}) by (phase, namespace)
```
- **Visualization**: Pie chart
- **Title**: Pod Status Distribution

### Panel 3: CPU Usage - Top 10 Pods
```promql
topk(10, sum(rate(container_cpu_usage_seconds_total{namespace=~"crypto-.*", container!="POD", container!=""}[5m])) by (pod, namespace))
```
- **Visualization**: Time series
- **Unit**: percent (0-100)
- **Title**: Top 10 CPU Usage by Pod

### Panel 4: Memory Usage - Top 10 Pods
```promql
topk(10, sum(container_memory_working_set_bytes{namespace=~"crypto-.*", container!="POD", container!=""}) by (pod, namespace))
```
- **Visualization**: Time series
- **Unit**: bytes (IEC)
- **Title**: Top 10 Memory Usage by Pod

### Panel 5: Total CPU Usage by Component
```promql
sum(rate(container_cpu_usage_seconds_total{namespace=~"crypto-.*", container!="POD"}[5m])) by (namespace)
```
- **Visualization**: Time series
- **Unit**: cores
- **Title**: Total CPU Usage by Namespace

### Panel 6: Total Memory Usage by Component
```promql
sum(container_memory_working_set_bytes{namespace=~"crypto-.*", container!="POD"}) by (namespace)
```
- **Visualization**: Time series
- **Unit**: bytes (IEC)
- **Title**: Total Memory Usage by Namespace

### Panel 7: Pod Restart Count
```promql
sum(increase(kube_pod_container_status_restarts_total{namespace=~"crypto-.*"}[1h])) by (pod, namespace)
```
- **Visualization**: Bar chart
- **Title**: Pod Restarts (Last Hour)

### Panel 8: Failed Pods
```promql
kube_pod_status_phase{namespace=~"crypto-.*", phase="Failed"}
```
- **Visualization**: Table
- **Title**: Failed Pods

---

## Dashboard Backend FastAPI

### Panel 1: HTTP Request Rate
```promql
sum(rate(http_requests_total{namespace="crypto-app", app="backend-fastapi"}[5m])) by (method, endpoint)
```
- **Visualization**: Time series
- **Title**: HTTP Request Rate by Method and Endpoint

### Panel 2: HTTP Request Duration (p95)
```promql
histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket{namespace="crypto-app", app="backend-fastapi"}[5m])) by (le, endpoint))
```
- **Visualization**: Time series
- **Unit**: seconds
- **Title**: HTTP Request Duration (p95)

### Panel 3: HTTP Status Codes
```promql
sum(rate(http_requests_total{namespace="crypto-app", app="backend-fastapi"}[5m])) by (status_code)
```
- **Visualization**: Time series
- **Title**: HTTP Status Codes

### Panel 4: Active Connections
```promql
http_server_connections_active{namespace="crypto-app", app="backend-fastapi"}
```
- **Visualization**: Stat
- **Title**: Active Connections

### Panel 5: Backend Pod CPU Usage
```promql
sum(rate(container_cpu_usage_seconds_total{namespace="crypto-app", pod=~"backend.*"}[5m])) by (pod)
```
- **Visualization**: Time series
- **Unit**: percent (0-100)
- **Title**: Backend CPU Usage

### Panel 6: Backend Pod Memory Usage
```promql
sum(container_memory_working_set_bytes{namespace="crypto-app", pod=~"backend.*"}) by (pod)
```
- **Visualization**: Time series
- **Unit**: bytes (IEC)
- **Title**: Backend Memory Usage

### Panel 7: Error Rate
```promql
sum(rate(http_requests_total{namespace="crypto-app", app="backend-fastapi", status_code=~"5.."}[5m]))
```
- **Visualization**: Time series
- **Title**: Error Rate (5xx)

### Panel 8: Request Latency (Average)
```promql
sum(rate(http_request_duration_seconds_sum{namespace="crypto-app", app="backend-fastapi"}[5m])) / sum(rate(http_request_duration_seconds_count{namespace="crypto-app", app="backend-fastapi"}[5m]))
```
- **Visualization**: Time series
- **Unit**: seconds
- **Title**: Average Request Latency

---

## Dashboard Kafka

### Panel 1: Kafka Broker CPU Usage
```promql
sum(rate(container_cpu_usage_seconds_total{namespace="crypto-infra", pod=~"my-cluster.*"}[5m])) by (pod)
```
- **Visualization**: Time series
- **Unit**: percent (0-100)
- **Title**: Kafka Broker CPU Usage

### Panel 2: Kafka Broker Memory Usage
```promql
sum(container_memory_working_set_bytes{namespace="crypto-infra", pod=~"my-cluster.*"}) by (pod)
```
- **Visualization**: Time series
- **Unit**: bytes (IEC)
- **Title**: Kafka Broker Memory Usage

### Panel 3: Kafka Messages In Per Second
```promql
sum(rate(kafka_server_brokertopicmetrics_messagesin_total{namespace="crypto-infra"}[5m])) by (topic)
```
- **Visualization**: Time series
- **Title**: Messages In Rate by Topic

### Panel 4: Kafka Messages Out Per Second
```promql
sum(rate(kafka_server_brokertopicmetrics_messagesout_total{namespace="crypto-infra"}[5m])) by (topic)
```
- **Visualization**: Time series
- **Title**: Messages Out Rate by Topic

### Panel 5: Kafka Bytes In Per Second
```promql
sum(rate(kafka_server_brokertopicmetrics_bytesin_total{namespace="crypto-infra"}[5m])) by (topic)
```
- **Visualization**: Time series
- **Unit**: bytes/sec
- **Title**: Bytes In Rate by Topic

### Panel 6: Kafka Bytes Out Per Second
```promql
sum(rate(kafka_server_brokertopicmetrics_bytesout_total{namespace="crypto-infra"}[5m])) by (topic)
```
- **Visualization**: Time series
- **Unit**: bytes/sec
- **Title**: Bytes Out Rate by Topic

### Panel 7: Kafka Consumer Lag
```promql
sum(kafka_consumer_lag_sum{namespace="crypto-infra"}) by (consumer_group, topic)
```
- **Visualization**: Time series
- **Title**: Consumer Lag by Group and Topic

### Panel 8: Kafka Partition Count
```promql
count(kafka_controller_offlinepartitionscount{namespace="crypto-infra"}) by (topic)
```
- **Visualization**: Stat
- **Title**: Partition Count by Topic

### Panel 9: Kafka Active Controller Count
```promql
kafka_controller_activecontrollercount{namespace="crypto-infra"}
```
- **Visualization**: Stat
- **Title**: Active Controller Count

### Panel 10: Kafka Under Replicated Partitions
```promql
sum(kafka_controller_underreplicatedpartitions{namespace="crypto-infra"})
```
- **Visualization**: Stat
- **Title**: Under Replicated Partitions

---

## Dashboard Airflow

### Panel 1: Airflow Pods CPU Usage
```promql
sum(rate(container_cpu_usage_seconds_total{namespace="crypto-infra", pod=~"airflow.*"}[5m])) by (pod)
```
- **Visualization**: Time series
- **Unit**: percent (0-100)
- **Title**: Airflow Pods CPU Usage

### Panel 2: Airflow Pods Memory Usage
```promql
sum(container_memory_working_set_bytes{namespace="crypto-infra", pod=~"airflow.*"}) by (pod)
```
- **Visualization**: Time series
- **Unit**: bytes (IEC)
- **Title**: Airflow Pods Memory Usage

### Panel 3: Airflow DAG Run Status
```promql
sum(airflow_dagrun_status{namespace="crypto-infra"}) by (dag_id, state)
```
- **Visualization**: Pie chart
- **Title**: DAG Run Status Distribution

### Panel 4: Airflow Task Instance Status
```promql
sum(airflow_task_instance_status{namespace="crypto-infra"}) by (dag_id, task_id, state)
```
- **Visualization**: Table
- **Title**: Task Instance Status

### Panel 5: Airflow DAG Run Duration
```promql
histogram_quantile(0.95, sum(rate(airflow_dagrun_duration_seconds_bucket{namespace="crypto-infra"}[5m])) by (le, dag_id))
```
- **Visualization**: Time series
- **Unit**: seconds
- **Title**: DAG Run Duration (p95) by DAG

### Panel 6: Airflow Task Duration
```promql
histogram_quantile(0.95, sum(rate(airflow_task_duration_seconds_bucket{namespace="crypto-infra"}[5m])) by (le, dag_id, task_id))
```
- **Visualization**: Time series
- **Unit**: seconds
- **Title**: Task Duration (p95) by DAG and Task

### Panel 7: Airflow Failed Tasks Count
```promql
sum(airflow_task_instance_status{namespace="crypto-infra", state="failed"}) by (dag_id)
```
- **Visualization**: Bar chart
- **Title**: Failed Tasks by DAG

### Panel 8: Airflow Scheduler Heartbeat
```promql
airflow_scheduler_heartbeat{namespace="crypto-infra"}
```
- **Visualization**: Stat
- **Title**: Scheduler Heartbeat

### Panel 9: Airflow Active DAG Runs
```promql
sum(airflow_dagrun_status{namespace="crypto-infra", state="running"}) by (dag_id)
```
- **Visualization**: Stat
- **Title**: Active DAG Runs

### Panel 10: Airflow Queued Tasks
```promql
sum(airflow_task_instance_status{namespace="crypto-infra", state="queued"})
```
- **Visualization**: Stat
- **Title**: Queued Tasks

---

## Dashboard Spark Operator

### Panel 1: Spark Operator Pods CPU Usage
```promql
sum(rate(container_cpu_usage_seconds_total{namespace="crypto-infra", pod=~"spark-kubernetes-operator.*"}[5m])) by (pod)
```
- **Visualization**: Time series
- **Unit**: percent (0-100)
- **Title**: Spark Operator CPU Usage

### Panel 2: Spark Operator Pods Memory Usage
```promql
sum(container_memory_working_set_bytes{namespace="crypto-infra", pod=~"spark-kubernetes-operator.*"}) by (pod)
```
- **Visualization**: Time series
- **Unit**: bytes (IEC)
- **Title**: Spark Operator Memory Usage

### Panel 3: Spark Applications Running
```promql
count(kube_pod_info{namespace="crypto-infra", pod=~"spark.*-driver.*"})
```
- **Visualization**: Stat
- **Title**: Running Spark Applications

### Panel 4: Spark Driver Pods CPU
```promql
sum(rate(container_cpu_usage_seconds_total{namespace="crypto-infra", pod=~"spark.*-driver.*"}[5m])) by (pod)
```
- **Visualization**: Time series
- **Unit**: percent (0-100)
- **Title**: Spark Driver CPU Usage

### Panel 5: Spark Driver Pods Memory
```promql
sum(container_memory_working_set_bytes{namespace="crypto-infra", pod=~"spark.*-driver.*"}) by (pod)
```
- **Visualization**: Time series
- **Unit**: bytes (IEC)
- **Title**: Spark Driver Memory Usage

### Panel 6: Spark Executor Pods CPU
```promql
sum(rate(container_cpu_usage_seconds_total{namespace="crypto-infra", pod=~"spark.*-exec.*"}[5m])) by (pod)
```
- **Visualization**: Time series
- **Unit**: percent (0-100)
- **Title**: Spark Executor CPU Usage

### Panel 7: Spark Executor Pods Memory
```promql
sum(container_memory_working_set_bytes{namespace="crypto-infra", pod=~"spark.*-exec.*"}) by (pod)
```
- **Visualization**: Time series
- **Unit**: bytes (IEC)
- **Title**: Spark Executor Memory Usage

### Panel 8: Spark Application Status
```promql
kube_pod_status_phase{namespace="crypto-infra", pod=~"spark.*"}
```
- **Visualization**: Pie chart
- **Title**: Spark Application Status

---

## Dashboard MongoDB

### Panel 1: MongoDB Pods CPU Usage
```promql
sum(rate(container_cpu_usage_seconds_total{namespace="crypto-infra", pod=~"my-mongo.*"}[5m])) by (pod)
```
- **Visualization**: Time series
- **Unit**: percent (0-100)
- **Title**: MongoDB CPU Usage

### Panel 2: MongoDB Pods Memory Usage
```promql
sum(container_memory_working_set_bytes{namespace="crypto-infra", pod=~"my-mongo.*"}) by (pod)
```
- **Visualization**: Time series
- **Unit**: bytes (IEC)
- **Title**: MongoDB Memory Usage

### Panel 3: MongoDB Connections
```promql
mongodb_connections{namespace="crypto-infra", state="current"}
```
- **Visualization**: Stat
- **Title**: Current Connections

### Panel 4: MongoDB Operations Per Second
```promql
sum(rate(mongodb_opcounters{namespace="crypto-infra"}[5m])) by (type)
```
- **Visualization**: Time series
- **Title**: Operations Per Second by Type

### Panel 5: MongoDB Network Bytes In
```promql
sum(rate(mongodb_network_bytes{namespace="crypto-infra", direction="in"}[5m]))
```
- **Visualization**: Time series
- **Unit**: bytes/sec
- **Title**: Network Bytes In

### Panel 6: MongoDB Network Bytes Out
```promql
sum(rate(mongodb_network_bytes{namespace="crypto-infra", direction="out"}[5m]))
```
- **Visualization**: Time series
- **Unit**: bytes/sec
- **Title**: Network Bytes Out

### Panel 7: MongoDB Replication Lag
```promql
mongodb_replset_member_replication_lag{namespace="crypto-infra"}
```
- **Visualization**: Time series
- **Unit**: seconds
- **Title**: Replication Lag

### Panel 8: MongoDB Cache Hit Ratio
```promql
mongodb_cache_ratio{namespace="crypto-infra"}
```
- **Visualization**: Time series
- **Unit**: percent (0-100)
- **Title**: Cache Hit Ratio

---

## Dashboard Redis

### Panel 1: Redis Pods CPU Usage
```promql
sum(rate(container_cpu_usage_seconds_total{namespace="crypto-infra", pod=~"my-redis.*"}[5m])) by (pod)
```
- **Visualization**: Time series
- **Unit**: percent (0-100)
- **Title**: Redis CPU Usage

### Panel 2: Redis Pods Memory Usage
```promql
sum(container_memory_working_set_bytes{namespace="crypto-infra", pod=~"my-redis.*"}) by (pod)
```
- **Visualization**: Time series
- **Unit**: bytes (IEC)
- **Title**: Redis Memory Usage

### Panel 3: Redis Connected Clients
```promql
redis_connected_clients{namespace="crypto-infra"}
```
- **Visualization**: Stat
- **Title**: Connected Clients

### Panel 4: Redis Commands Per Second
```promql
sum(rate(redis_commands_total{namespace="crypto-infra"}[5m])) by (command)
```
- **Visualization**: Time series
- **Title**: Commands Per Second by Command

### Panel 5: Redis Keyspace Keys
```promql
redis_keyspace_keys{namespace="crypto-infra"}
```
- **Visualization**: Stat
- **Title**: Total Keys

### Panel 6: Redis Hit Rate
```promql
sum(rate(redis_keyspace_hits_total{namespace="crypto-infra"}[5m])) / (sum(rate(redis_keyspace_hits_total{namespace="crypto-infra"}[5m])) + sum(rate(redis_keyspace_misses_total{namespace="crypto-infra"}[5m])))
```
- **Visualization**: Time series
- **Unit**: percent (0-100)
- **Title**: Cache Hit Rate

### Panel 7: Redis Memory Used
```promql
redis_memory_used_bytes{namespace="crypto-infra"}
```
- **Visualization**: Time series
- **Unit**: bytes (IEC)
- **Title**: Memory Used

### Panel 8: Redis Evicted Keys
```promql
sum(rate(redis_evicted_keys_total{namespace="crypto-infra"}[5m]))
```
- **Visualization**: Time series
- **Title**: Evicted Keys Per Second

---

## Dashboard Kubernetes Resources

### Panel 1: Node CPU Usage
```promql
(1 - avg(rate(node_cpu_seconds_total{mode="idle"}[5m]))) * 100
```
- **Visualization**: Time series
- **Unit**: percent (0-100)
- **Title**: Node CPU Usage

### Panel 2: Node Memory Usage
```promql
(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100
```
- **Visualization**: Time series
- **Unit**: percent (0-100)
- **Title**: Node Memory Usage

### Panel 3: Node Disk Usage
```promql
(1 - (node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"})) * 100
```
- **Visualization**: Time series
- **Unit**: percent (0-100)
- **Title**: Node Disk Usage

### Panel 4: Pod CPU Requests vs Limits
```promql
sum(kube_pod_container_resource_requests{namespace=~"crypto-.*", resource="cpu"}) by (namespace)
```
- **Visualization**: Time series
- **Unit**: cores
- **Title**: CPU Requests

```promql
sum(kube_pod_container_resource_limits{namespace=~"crypto-.*", resource="cpu"}) by (namespace)
```
- **Visualization**: Time series
- **Unit**: cores
- **Title**: CPU Limits

### Panel 5: Pod Memory Requests vs Limits
```promql
sum(kube_pod_container_resource_requests{namespace=~"crypto-.*", resource="memory"}) by (namespace)
```
- **Visualization**: Time series
- **Unit**: bytes (IEC)
- **Title**: Memory Requests

```promql
sum(kube_pod_container_resource_limits{namespace=~"crypto-.*", resource="memory"}) by (namespace)
```
- **Visualization**: Time series
- **Unit**: bytes (IEC)
- **Title**: Memory Limits

### Panel 6: Deployment Replicas Status
```promql
kube_deployment_status_replicas{namespace=~"crypto-.*"}
```
- **Visualization**: Time series
- **Title**: Desired Replicas

```promql
kube_deployment_status_replicas_ready{namespace=~"crypto-.*"}
```
- **Visualization**: Time series
- **Title**: Ready Replicas

### Panel 7: Service Endpoints
```promql
kube_endpoint_address_available{namespace=~"crypto-.*"}
```
- **Visualization**: Stat
- **Title**: Available Endpoints

### Panel 8: Persistent Volume Claims
```promql
kube_persistentvolumeclaim_status_phase{namespace=~"crypto-.*"}
```
- **Visualization**: Pie chart
- **Title**: PVC Status

---

## Dashboard Network & Traffic

### Panel 1: Network Bytes Received
```promql
sum(rate(container_network_receive_bytes_total{namespace=~"crypto-.*"}[5m])) by (pod, namespace)
```
- **Visualization**: Time series
- **Unit**: bytes/sec
- **Title**: Network Bytes Received by Pod

### Panel 2: Network Bytes Transmitted
```promql
sum(rate(container_network_transmit_bytes_total{namespace=~"crypto-.*"}[5m])) by (pod, namespace)
```
- **Visualization**: Time series
- **Unit**: bytes/sec
- **Title**: Network Bytes Transmitted by Pod

### Panel 3: Network Packets Received
```promql
sum(rate(container_network_receive_packets_total{namespace=~"crypto-.*"}[5m])) by (pod, namespace)
```
- **Visualization**: Time series
- **Title**: Network Packets Received by Pod

### Panel 4: Network Packets Transmitted
```promql
sum(rate(container_network_transmit_packets_total{namespace=~"crypto-.*"}[5m])) by (pod, namespace)
```
- **Visualization**: Time series
- **Title**: Network Packets Transmitted by Pod

### Panel 5: Network Errors Received
```promql
sum(rate(container_network_receive_errors_total{namespace=~"crypto-.*"}[5m])) by (pod, namespace)
```
- **Visualization**: Time series
- **Title**: Network Errors Received

### Panel 6: Network Errors Transmitted
```promql
sum(rate(container_network_transmit_errors_total{namespace=~"crypto-.*"}[5m])) by (pod, namespace)
```
- **Visualization**: Time series
- **Title**: Network Errors Transmitted

---

## Cách Sử dụng

### Bước 1: Tạo Dashboard mới trong Grafana

1. Đăng nhập vào Grafana
2. Click **Dashboards** → **New** → **New Dashboard**
3. Click **Add visualization** để thêm panel mới

### Bước 2: Cấu hình Data Source

1. Chọn **Prometheus** làm data source
2. Đảm bảo Prometheus đã được cấu hình đúng

### Bước 3: Thêm Query

1. Copy một trong các query từ tài liệu này
2. Paste vào ô **Query** trong Grafana
3. Chọn **Visualization** phù hợp (Time series, Stat, Pie chart, etc.)
4. Cấu hình **Unit** và **Title** cho panel

### Bước 4: Tùy chỉnh Dashboard

- Thêm **Variables** để filter theo namespace, pod, etc.
- Sử dụng **Transformations** để xử lý dữ liệu
- Thêm **Annotations** để đánh dấu các sự kiện quan trọng
- Cấu hình **Alerting** nếu cần

---

## Variables cho Dashboard (Tùy chọn)

Thêm các variables sau để filter dữ liệu:

### Variable: namespace
- **Type**: Query
- **Query**: `label_values(kube_pod_info, namespace)`
- **Label**: Namespace

### Variable: pod
- **Type**: Query
- **Query**: `label_values(kube_pod_info{namespace="$namespace"}, pod)`
- **Label**: Pod

### Variable: dag_id
- **Type**: Query
- **Query**: `label_values(airflow_dagrun_status, dag_id)`
- **Label**: DAG ID

---

## Alert Rules (Ví dụ)

### Alert: High CPU Usage
```yaml
- alert: HighCPUUsage
  expr: sum(rate(container_cpu_usage_seconds_total{namespace=~"crypto-.*"}[5m])) by (pod) > 0.8
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "High CPU usage on {{ $labels.pod }}"
```

### Alert: High Memory Usage
```yaml
- alert: HighMemoryUsage
  expr: sum(container_memory_working_set_bytes{namespace=~"crypto-.*"}) by (pod) / sum(container_spec_memory_limit_bytes{namespace=~"crypto-.*"}) by (pod) > 0.9
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "High memory usage on {{ $labels.pod }}"
```

### Alert: Pod CrashLoopBackOff
```yaml
- alert: PodCrashLoopBackOff
  expr: kube_pod_status_phase{namespace=~"crypto-.*", phase="Failed"} > 0
  for: 2m
  labels:
    severity: critical
  annotations:
    summary: "Pod {{ $labels.pod }} is in Failed state"
```

---

## Troubleshooting

### Query không trả về dữ liệu?

1. **Kiểm tra Prometheus targets:**
   ```bash
   kubectl port-forward svc/crypto-monitoring-kube-prometheus-prometheus 9090:9090 -n crypto-monitoring
   # Mở: http://localhost:9090/targets
   ```

2. **Kiểm tra metrics có tồn tại:**
   ```bash
   # Trong Prometheus UI, thử query:
   {__name__=~".*"}
   ```

3. **Kiểm tra labels:**
   ```bash
   kubectl get pods -n crypto-infra --show-labels
   ```

4. **Kiểm tra ServiceMonitor:**
   ```bash
   kubectl get servicemonitors -A
   ```

### Metrics không hiển thị?

- Đảm bảo ServiceMonitor đã được apply
- Kiểm tra Prometheus có scrape được targets không
- Xem logs của Prometheus để tìm lỗi

---

## Tài liệu tham khảo

- [Prometheus Query Language (PromQL)](https://prometheus.io/docs/prometheus/latest/querying/basics/)
- [Grafana Dashboard Documentation](https://grafana.com/docs/grafana/latest/dashboards/)
- [Kubernetes Metrics](https://github.com/kubernetes/kube-state-metrics)
- [Prometheus Operator](https://github.com/prometheus-operator/prometheus-operator)

