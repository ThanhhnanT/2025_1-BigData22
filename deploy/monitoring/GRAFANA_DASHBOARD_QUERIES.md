# Hướng dẫn Tạo Grafana Dashboard cho Hệ thống Crypto

Tài liệu này cung cấp các câu truy vấn PromQL để tạo dashboard Grafana cho hệ thống monitoring hiện tại.

## ⚠️ Lưu ý quan trọng về Queries

**Vấn đề phổ biến:** Metric `container_cpu_usage_seconds_total` và `container_memory_working_set_bytes` có thể **KHÔNG có label `namespace` trực tiếp** trong một số cấu hình Prometheus.

**Giải pháp:** Sử dụng các query dưới đây với join `kube_pod_info` hoặc filter theo pod name pattern.

## Quick Start - Test Queries (Đơn giản nhất)

### Test 1: CPU Usage - Tất cả Pods (Không filter namespace)
```promql
topk(10, sum(rate(container_cpu_usage_seconds_total{container!="POD", container!=""}[5m])) by (pod))
```

### Test 2: CPU Usage - Với namespace (Join với kube_pod_info)
```promql
topk(10, sum(rate(container_cpu_usage_seconds_total{container!="POD", container!=""}[5m])) by (pod) * on (pod) group_left(namespace) kube_pod_info{namespace=~"crypto-.*"})
```

### Test 3: Memory Usage - Tất cả Pods
```promql
topk(10, sum(container_memory_working_set_bytes{container!="POD", container!=""}) by (pod))
```

### Test 4: Kiểm tra metric có label namespace không
```promql
# Nếu query này trả về kết quả, metric có label namespace:
container_cpu_usage_seconds_total{namespace=~"crypto-.*"}

# Nếu không, sử dụng join:
container_cpu_usage_seconds_total * on (pod) group_left(namespace) kube_pod_info{namespace=~"crypto-.*"}
```

---

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

**Hoặc nếu namespace label có sẵn:**
```promql
topk(10, sum(rate(container_cpu_usage_seconds_total{container!="POD", container!=""}[5m])) by (pod, namespace))
```

**Hoặc filter theo pod name pattern:**
```promql
topk(10, sum(rate(container_cpu_usage_seconds_total{pod=~".*", container!="POD", container!=""}[5m])) by (pod) * on (pod) group_left(namespace) kube_pod_info{namespace=~"crypto-.*"})
```

### Panel 4: Memory Usage - Top 10 Pods
```promql
topk(10, sum(container_memory_working_set_bytes{container!="POD", container!=""}) by (pod) * on (pod) group_left(namespace) kube_pod_info{namespace=~"crypto-.*"})
```
- **Visualization**: Time series
- **Unit**: bytes (IEC)
- **Title**: Top 10 Memory Usage by Pod

**Hoặc nếu namespace label có sẵn:**
```promql
topk(10, sum(container_memory_working_set_bytes{container!="POD", container!=""}) by (pod, namespace))
```

### Panel 5: Total CPU Usage by Component
```promql
sum(rate(container_cpu_usage_seconds_total{namespace=~"crypto-.*", container!="POD"}[5m])) by (namespace)
```
- **Visualization**: Time series
- **Unit**: cores
- **Title**: Total CPU Usage by Namespace

**Hoặc cách đơn giản hơn:**
```promql
sum(rate(container_cpu_usage_seconds_total{container!="POD"}[5m])) by (pod) * on (pod) group_left(namespace) kube_pod_info{namespace=~"crypto-.*"} | sum by (namespace)
```

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

> **⚠️ Lưu ý:** Backend FastAPI hiện tại chưa có Prometheus HTTP instrumentation. Các panel 1-4, 7-8 sử dụng Kubernetes/process metrics thay thế. Để có HTTP metrics, xem phần [Thêm HTTP Metrics](#thêm-http-metrics-cho-backend-fastapi) ở cuối file.

### Panel 1: Backend Pod Status
```promql
kube_pod_status_phase{namespace="crypto-app", pod=~"backend.*"}
```
- **Visualization**: Stat
- **Title**: Pod Status
- **Value options**: Last value

### Panel 2: Backend Pod Restart Count
```promql
sum(increase(kube_pod_container_status_restarts_total{namespace="crypto-app", pod=~"backend.*"}[1h])) by (pod)
```
- **Visualization**: Stat
- **Title**: Pod Restarts (Last Hour)

### Panel 3: Network Bytes Received
```promql
sum(rate(container_network_receive_bytes_total{namespace="crypto-app", pod=~"backend.*"}[5m])) by (pod)
```
- **Visualization**: Time series
- **Unit**: bytes/sec
- **Title**: Network Bytes Received

### Panel 4: Network Bytes Transmitted
```promql
sum(rate(container_network_transmit_bytes_total{namespace="crypto-app", pod=~"backend.*"}[5m])) by (pod)
```
- **Visualization**: Time series
- **Unit**: bytes/sec
- **Title**: Network Bytes Transmitted

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

### Panel 7: CPU Throttling
```promql
sum(rate(container_cpu_cfs_throttled_seconds_total{namespace="crypto-app", pod=~"backend.*"}[5m])) by (pod)
```
- **Visualization**: Time series
- **Unit**: seconds/sec
- **Title**: CPU Throttling

### Panel 8: Memory Limit Usage Percentage
```promql
(sum(container_memory_working_set_bytes{namespace="crypto-app", pod=~"backend.*"}) by (pod) / sum(container_spec_memory_limit_bytes{namespace="crypto-app", pod=~"backend.*"}) by (pod)) * 100
```
- **Visualization**: Time series
- **Unit**: percent (0-100)
- **Title**: Memory Usage % of Limit

### Panel 9: Pod Ready Status
```promql
kube_pod_status_condition{namespace="crypto-app", pod=~"backend.*", condition="Ready"}
```
- **Visualization**: Stat
- **Title**: Pod Ready Status
- **Value options**: Last value

### Panel 10: Container Restart Count
```promql
kube_pod_container_status_restarts_total{namespace="crypto-app", pod=~"backend.*"}
```
- **Visualization**: Time series
- **Title**: Container Restart Count Over Time

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
> **⚠️ Lưu ý:** Metric names phụ thuộc vào cấu hình JMX Prometheus Exporter. Nếu query không hoạt động, xem phần [Troubleshooting Kafka Metrics](#troubleshooting-kafka-metrics) ở cuối file.

**Query 1 (JMX Exporter format - phổ biến nhất):**
```promql
sum(rate(kafka_server_BrokerTopicMetrics_MessagesInPerSec_Count[5m])) by (topic)
```

**Query 2 (Alternative format):**
```promql
sum(rate(kafka_server_BrokerTopicMetrics_MessagesInPerSec_OneMinuteRate[5m])) by (topic)
```

**Query 3 (Nếu có label pod):**
```promql
sum(rate(kafka_server_BrokerTopicMetrics_MessagesInPerSec_Count{pod=~"my-cluster.*"}[5m])) by (topic, pod)
```

- **Visualization**: Time series
- **Title**: Messages In Rate by Topic

### Panel 4: Kafka Messages Out Per Second
**Query 1 (JMX Exporter format):**
```promql
sum(rate(kafka_server_BrokerTopicMetrics_MessagesOutPerSec_Count[5m])) by (topic)
```

**Query 2 (Alternative format):**
```promql
sum(rate(kafka_server_BrokerTopicMetrics_MessagesOutPerSec_OneMinuteRate[5m])) by (topic)
```

- **Visualization**: Time series
- **Title**: Messages Out Rate by Topic

### Panel 5: Kafka Bytes In Per Second
**Query 1 (JMX Exporter format):**
```promql
sum(rate(kafka_server_BrokerTopicMetrics_BytesInPerSec_Count[5m])) by (topic)
```

**Query 2 (Alternative format):**
```promql
sum(rate(kafka_server_BrokerTopicMetrics_BytesInPerSec_OneMinuteRate[5m])) by (topic)
```

- **Visualization**: Time series
- **Unit**: bytes/sec
- **Title**: Bytes In Rate by Topic

### Panel 6: Kafka Bytes Out Per Second
**Query 1 (JMX Exporter format):**
```promql
sum(rate(kafka_server_BrokerTopicMetrics_BytesOutPerSec_Count[5m])) by (topic)
```

**Query 2 (Alternative format):**
```promql
sum(rate(kafka_server_BrokerTopicMetrics_BytesOutPerSec_OneMinuteRate[5m])) by (topic)
```

- **Visualization**: Time series
- **Unit**: bytes/sec
- **Title**: Bytes Out Rate by Topic

### Panel 7: Kafka Consumer Lag
> **⚠️ Lưu ý:** Consumer lag metrics thường được expose bởi Kafka Exporter hoặc JMX exporter với format khác.

**Query 1 (JMX Exporter - Consumer Lag):**
```promql
sum(kafka_consumer_consumer_lag_sum) by (consumer_group, topic)
```

**Query 2 (Alternative - nếu có label pod):**
```promql
sum(kafka_consumer_consumer_lag_sum{pod=~"my-cluster.*"}) by (consumer_group, topic, pod)
```

**Query 3 (Nếu sử dụng Kafka Exporter riêng):**
```promql
sum(kafka_consumer_lag_sum) by (consumer_group, topic)
```

- **Visualization**: Time series
- **Title**: Consumer Lag by Group and Topic

### Panel 8: Kafka Partition Count
**Query 1 (JMX Exporter format):**
```promql
kafka_controller_OfflinePartitionsCount_Value
```

**Query 2 (Alternative - Count partitions từ topic metrics):**
```promql
count(kafka_server_BrokerTopicMetrics_MessagesInPerSec_Count) by (topic)
```

- **Visualization**: Stat
- **Title**: Partition Count by Topic

### Panel 9: Kafka Active Controller Count
**Query 1 (JMX Exporter format):**
```promql
kafka_controller_KafkaController_ActiveControllerCount_Value
```

**Query 2 (Alternative format):**
```promql
kafka_controller_ActiveControllerCount_Value
```

- **Visualization**: Stat
- **Title**: Active Controller Count

### Panel 10: Kafka Under Replicated Partitions
**Query 1 (JMX Exporter format):**
```promql
kafka_controller_OfflinePartitionsCount_Value
```

**Query 2 (Alternative - Under replicated partitions):**
```promql
kafka_controller_UnderReplicatedPartitions_Value
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

3. **Kiểm tra labels có sẵn trong metric:**
   ```promql
   # Kiểm tra xem metric có label namespace không:
   container_cpu_usage_seconds_total
   
   # Nếu không có namespace, cần join với kube_pod_info:
   container_cpu_usage_seconds_total * on (pod) group_left(namespace) kube_pod_info{namespace=~"crypto-.*"}
   ```

4. **Kiểm tra labels:**
   ```bash
   kubectl get pods -n crypto-infra --show-labels
   ```

5. **Kiểm tra ServiceMonitor:**
   ```bash
   kubectl get servicemonitors -A
   ```

### Sửa Query CPU Usage không chạy được

**Vấn đề:** `container_cpu_usage_seconds_total` có thể không có label `namespace` trực tiếp.

**Giải pháp 1: Join với kube_pod_info (Khuyến nghị)**
```promql
topk(10, sum(rate(container_cpu_usage_seconds_total{container!="POD", container!=""}[5m])) by (pod) * on (pod) group_left(namespace) kube_pod_info{namespace=~"crypto-.*"})
```

**Giải pháp 2: Filter theo pod name pattern**
```promql
topk(10, sum(rate(container_cpu_usage_seconds_total{pod=~"airflow.*|kafka.*|spark.*|backend.*|redis.*|mongo.*", container!="POD", container!=""}[5m])) by (pod))
```

**Giải pháp 3: Sử dụng label namespace nếu có sẵn**
```promql
topk(10, sum(rate(container_cpu_usage_seconds_total{namespace=~"crypto-.*", container!="POD", container!=""}[5m])) by (pod, namespace))
```

**Giải pháp 4: Query đơn giản nhất (không filter namespace)**
```promql
topk(10, sum(rate(container_cpu_usage_seconds_total{container!="POD", container!=""}[5m])) by (pod))
```

### Debug Query Step by Step

1. **Bước 1: Kiểm tra metric có tồn tại:**
   ```promql
   container_cpu_usage_seconds_total
   ```

2. **Bước 2: Xem các labels có sẵn:**
   ```promql
   {__name__="container_cpu_usage_seconds_total"}
   ```

3. **Bước 3: Test với filter đơn giản:**
   ```promql
   container_cpu_usage_seconds_total{container!="POD"}
   ```

4. **Bước 4: Thêm rate:**
   ```promql
   rate(container_cpu_usage_seconds_total{container!="POD"}[5m])
   ```

5. **Bước 5: Thêm sum và group by:**
   ```promql
   sum(rate(container_cpu_usage_seconds_total{container!="POD"}[5m])) by (pod)
   ```

6. **Bước 6: Thêm topk:**
   ```promql
   topk(10, sum(rate(container_cpu_usage_seconds_total{container!="POD"}[5m])) by (pod))
   ```

7. **Bước 7: Thêm filter namespace (nếu cần):**
   ```promql
   topk(10, sum(rate(container_cpu_usage_seconds_total{container!="POD"}[5m])) by (pod) * on (pod) group_left(namespace) kube_pod_info{namespace=~"crypto-.*"})
   ```

### Metrics không hiển thị?

- Đảm bảo ServiceMonitor đã được apply
- Kiểm tra Prometheus có scrape được targets không
- Xem logs của Prometheus để tìm lỗi
- Kiểm tra xem metric có label `namespace` hay không bằng cách query trực tiếp trong Prometheus UI

### Troubleshooting Kafka Metrics

**Vấn đề:** Các query từ Panel 3 trở đi không trả về dữ liệu (no data).

**Nguyên nhân phổ biến:**
1. Kafka metrics chưa được bật trong cấu hình Kafka cluster
2. Metric names không đúng với format của JMX Prometheus Exporter
3. ServiceMonitor chưa được cấu hình đúng
4. Metrics endpoint không được expose

**Bước 1: Kiểm tra Kafka metrics có được bật không**

Kiểm tra cấu hình Kafka cluster:
```bash
kubectl get kafka my-cluster -n crypto-infra -o yaml | grep -A 10 metricsConfig
```

Nếu không có `metricsConfig`, cần thêm vào file `Kafka/kafka-helm.yaml`:
```yaml
spec:
  kafka:
    metricsConfig:
      type: jmxPrometheusExporter
      valueFrom:
        configMapKeyRef:
          name: kafka-metrics-config
          key: kafka-metrics-config.yml
```

**Bước 2: Kiểm tra ServiceMonitor**

```bash
kubectl get servicemonitor kafka-cluster -n crypto-infra -o yaml
```

Đảm bảo ServiceMonitor có:
- Label `release: crypto-monitoring` (hoặc label phù hợp với Prometheus selector)
- Endpoint trỏ đúng port `tcp-prometheus`
- Path `/metrics`

**Bước 3: Kiểm tra Prometheus có scrape được Kafka không**

```bash
# Port-forward Prometheus
kubectl port-forward svc/crypto-monitoring-kube-prometheus-prometheus 9090:9090 -n crypto-monitoring

# Mở browser: http://localhost:9090/targets
# Tìm target có tên chứa "kafka" hoặc "my-cluster"
```

**Bước 4: Tìm metric names thực tế**

Trong Prometheus UI (http://localhost:9090), thử các query sau để tìm metric names:

```promql
# Tìm tất cả metrics có chứa "kafka"
{__name__=~"kafka.*"}

# Tìm metrics về messages
{__name__=~".*[Mm]essage.*"}

# Tìm metrics về bytes
{__name__=~".*[Bb]yte.*"}

# Tìm metrics về topic
{__name__=~".*[Tt]opic.*"}

# Tìm metrics về controller
{__name__=~".*[Cc]ontroller.*"}
```

**Bước 5: Kiểm tra metrics endpoint trực tiếp**

```bash
# Lấy tên pod Kafka
kubectl get pods -n crypto-infra -l strimzi.io/cluster=my-cluster

# Port-forward đến metrics endpoint (thường là port 9404)
kubectl port-forward <kafka-pod-name> 9404:9404 -n crypto-infra

# Kiểm tra metrics
curl http://localhost:9404/metrics | grep -i kafka | head -20
```

**Bước 6: Sử dụng query đơn giản để test**

Thử query đơn giản nhất để xem có metric nào không:
```promql
# Tìm tất cả metrics từ Kafka pods
{__name__=~"kafka.*", pod=~"my-cluster.*"}

# Hoặc không filter pod
{__name__=~"kafka.*"}
```

**Bước 7: Kiểm tra JMX Exporter ConfigMap**

Nếu sử dụng JMX Prometheus Exporter, cần có ConfigMap với cấu hình:
```bash
kubectl get configmap kafka-metrics-config -n crypto-infra -o yaml
```

ConfigMap này định nghĩa các metrics nào được expose và format của chúng.

**Giải pháp thay thế: Sử dụng Network metrics**

Nếu Kafka metrics không hoạt động, có thể sử dụng network metrics như proxy:
```promql
# Network bytes received (proxy cho messages in)
sum(rate(container_network_receive_bytes_total{pod=~"my-cluster.*"}[5m])) by (pod)

# Network bytes transmitted (proxy cho messages out)
sum(rate(container_network_transmit_bytes_total{pod=~"my-cluster.*"}[5m])) by (pod)
```

**Lưu ý quan trọng:**
- Metric names từ JMX Prometheus Exporter thường có format: `kafka_<domain>_<bean>_<attribute>_<type>`
- Format có thể khác nhau tùy vào version của JMX exporter và cấu hình
- Luôn kiểm tra `/metrics` endpoint trực tiếp để xem metric names thực tế

---

## Thêm HTTP Metrics cho Backend FastAPI

Nếu bạn muốn có HTTP metrics (request rate, latency, status codes) cho Backend FastAPI, làm theo các bước sau:

### Bước 1: Cài đặt Prometheus Instrumentator

Thêm vào `backend_fastapi/requirements.txt`:
```txt
prometheus-fastapi-instrumentator==7.0.0
```

### Bước 2: Cập nhật main.py

Thêm vào `backend_fastapi/app/main.py`:
```python
from prometheus_fastapi_instrumentator import Instrumentator

# Thêm sau khi tạo app (sau dòng app = FastAPI(...))
instrumentator = Instrumentator()
instrumentator.instrument(app).expose(app)
```

### Bước 3: Rebuild và Deploy

```bash
cd backend_fastapi
docker build -t your-registry/backend-fastapi:latest .
docker push your-registry/backend-fastapi:latest
kubectl rollout restart deployment/backend-fastapi -n crypto-app
```

### Bước 4: Verify Metrics Endpoint

```bash
kubectl port-forward svc/backend-fastapi-service 8000:8000 -n crypto-app
curl http://localhost:8000/metrics
```

### Bước 5: Sử dụng HTTP Metrics Queries

Sau khi bật instrumentation, bạn có thể sử dụng các queries sau:

#### HTTP Request Rate
```promql
sum(rate(http_requests_total{namespace="crypto-app", app="backend-fastapi"}[5m])) by (method, endpoint)
```

#### HTTP Request Duration (p95)
```promql
histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket{namespace="crypto-app", app="backend-fastapi"}[5m])) by (le, endpoint))
```

#### HTTP Status Codes
```promql
sum(rate(http_requests_total{namespace="crypto-app", app="backend-fastapi"}[5m])) by (status_code)
```

#### Error Rate (5xx)
```promql
sum(rate(http_requests_total{namespace="crypto-app", app="backend-fastapi", status_code=~"5.."}[5m]))
```

#### Average Request Latency
```promql
sum(rate(http_request_duration_seconds_sum{namespace="crypto-app", app="backend-fastapi"}[5m])) / sum(rate(http_request_duration_seconds_count{namespace="crypto-app", app="backend-fastapi"}[5m]))
```

**Lưu ý:** Các metric names có thể khác tùy theo version của `prometheus-fastapi-instrumentator`. Kiểm tra `/metrics` endpoint để xem metric names thực tế.

---

## Tài liệu tham khảo

- [Prometheus Query Language (PromQL)](https://prometheus.io/docs/prometheus/latest/querying/basics/)
- [Grafana Dashboard Documentation](https://grafana.com/docs/grafana/latest/dashboards/)
- [Kubernetes Metrics](https://github.com/kubernetes/kube-state-metrics)
- [Prometheus Operator](https://github.com/prometheus-operator/prometheus-operator)
- [Prometheus FastAPI Instrumentator](https://github.com/trallnag/prometheus-fastapi-instrumentator)

