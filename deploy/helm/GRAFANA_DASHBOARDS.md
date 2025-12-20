# Hướng dẫn Sử dụng Dashboards trong Grafana

## Cách xem Dashboards có sẵn

### Bước 1: Vào phần Dashboards
1. Mở Grafana: http://<minikube-ip>:30002
2. Login: `admin` / `12345678`
3. Click vào **Dashboards** ở menu bên trái (biểu tượng 4 ô vuông)
4. Chọn **Browse** hoặc **Dashboards**

### Bước 2: Tìm và mở Dashboard
- Bạn sẽ thấy danh sách các dashboards có sẵn:
  - **Kubernetes / Compute Resources / Cluster** - Tổng quan tài nguyên cluster
  - **Kubernetes / Compute Resources / Namespace (Pods)** - Metrics pods theo namespace
  - **Kubernetes / Compute Resources / Pod** - Metrics chi tiết từng pod
  - **Kubernetes / Networking / Cluster** - Network metrics
  - **Alertmanager / Overview** - Alertmanager dashboard
  - **CoreDNS** - DNS metrics
  - **etcd** - etcd metrics

### Bước 3: Mở Dashboard
- Click vào tên dashboard để mở
- Dashboard sẽ hiển thị các panels với metrics

---

## Dashboards hữu ích cho hệ thống của bạn

### 1. Kubernetes / Compute Resources / Namespace (Pods)
**Dùng để xem:** CPU, Memory, Network của tất cả pods trong namespace

**Cách dùng:**
1. Mở dashboard
2. Chọn namespace: `crypto-infra` hoặc `crypto-app`
3. Xem metrics của các pods:
   - Airflow pods
   - Kafka pods
   - Spark Operator pods
   - Redis pods
   - MongoDB pods

### 2. Kubernetes / Compute Resources / Pod
**Dùng để xem:** Metrics chi tiết của một pod cụ thể

**Cách dùng:**
1. Mở dashboard
2. Chọn namespace: `crypto-infra`
3. Chọn pod từ dropdown (ví dụ: `airflow-scheduler-xxx`)
4. Xem CPU, Memory, Network chi tiết

### 3. Kubernetes / Compute Resources / Cluster
**Dùng để xem:** Tổng quan toàn bộ cluster

**Cách dùng:**
- Mở dashboard để xem:
  - Total CPU/Memory usage
  - Node metrics
  - Cluster-wide statistics

---

## Tạo Dashboard mới cho Services của bạn

### Dashboard cho Airflow

#### Bước 1: Tạo Dashboard mới
1. Click **Dashboards** → **New** → **New Dashboard**
2. Click **Add visualization**

#### Bước 2: Thêm Panel - Airflow Pods CPU
1. Chọn **Prometheus** data source
2. Query:
   ```promql
   sum(rate(container_cpu_usage_seconds_total{namespace="crypto-infra", pod=~"airflow.*", container!="POD"}[5m])) by (pod)
   ```
3. Visualization: **Time series**
4. Title: "Airflow Pods CPU Usage"
5. Unit: **percent (0-100)**

#### Bước 3: Thêm Panel - Airflow Pods Memory
1. Click **Add panel** → **Add visualization**
2. Query:
   ```promql
   sum(container_memory_working_set_bytes{namespace="crypto-infra", pod=~"airflow.*", container!="POD"}) by (pod)
   ```
3. Visualization: **Time series**
4. Title: "Airflow Pods Memory Usage"
5. Unit: **bytes (IEC)**

#### Bước 4: Thêm Panel - Airflow Pod Status
1. Click **Add panel** → **Add visualization**
2. Query:
   ```promql
   kube_pod_status_phase{namespace="crypto-infra", pod=~"airflow.*"}
   ```
3. Visualization: **Stat**
4. Title: "Airflow Pod Status"

#### Bước 5: Lưu Dashboard
1. Click **Save dashboard** (icon đĩa mềm)
2. Đặt tên: "Airflow Monitoring"
3. Chọn folder: **General** hoặc tạo folder mới

---

### Dashboard cho Kafka

#### Panel 1: Kafka Pods CPU
```promql
sum(rate(container_cpu_usage_seconds_total{namespace="crypto-infra", pod=~"my-cluster.*", container!="POD"}[5m])) by (pod)
```

#### Panel 2: Kafka Pods Memory
```promql
sum(container_memory_working_set_bytes{namespace="crypto-infra", pod=~"my-cluster.*", container!="POD"}) by (pod)
```

#### Panel 3: Kafka Pod Status
```promql
kube_pod_status_phase{namespace="crypto-infra", pod=~"my-cluster.*"}
```

---

### Dashboard cho Spark Operator

#### Panel 1: Spark Operator Pods CPU
```promql
sum(rate(container_cpu_usage_seconds_total{namespace="crypto-infra", pod=~"spark-kubernetes-operator.*", container!="POD"}[5m])) by (pod)
```

#### Panel 2: Spark Operator Pods Memory
```promql
sum(container_memory_working_set_bytes{namespace="crypto-infra", pod=~"spark-kubernetes-operator.*", container!="POD"}) by (pod)
```

---

### Dashboard tổng hợp cho tất cả Services

#### Panel 1: Top 10 Pods CPU Usage
```promql
topk(10, sum(rate(container_cpu_usage_seconds_total{namespace="crypto-infra", container!="POD"}[5m])) by (pod))
```
- Visualization: **Bar gauge**
- Title: "Top 10 Pods by CPU Usage"

#### Panel 2: Top 10 Pods Memory Usage
```promql
topk(10, sum(container_memory_working_set_bytes{namespace="crypto-infra", container!="POD"}) by (pod))
```
- Visualization: **Bar gauge**
- Title: "Top 10 Pods by Memory Usage"

#### Panel 3: Pods by Service Type
```promql
sum(rate(container_cpu_usage_seconds_total{namespace="crypto-infra", container!="POD"}[5m])) by (pod)
```
- Visualization: **Pie chart**
- Group by: **pod**

#### Panel 4: Total CPU Usage by Namespace
```promql
sum(rate(container_cpu_usage_seconds_total{namespace="crypto-infra", container!="POD"}[5m]))
```
- Visualization: **Stat**
- Title: "Total CPU Usage (crypto-infra)"

#### Panel 5: Total Memory Usage by Namespace
```promql
sum(container_memory_working_set_bytes{namespace="crypto-infra", container!="POD"})
```
- Visualization: **Stat**
- Title: "Total Memory Usage (crypto-infra)"
- Unit: **bytes (IEC)**

---

## Cách sử dụng Variables trong Dashboard

### Tạo Variable cho Namespace

1. Vào **Dashboard settings** (icon bánh răng)
2. Chọn **Variables** → **Add variable**
3. Cấu hình:
   - **Name**: `namespace`
   - **Type**: **Query**
   - **Data source**: **Prometheus**
   - **Query**: `label_values(kube_pod_info, namespace)`
   - **Label**: **Namespace**
   - **Multi-value**: ✅ (nếu muốn chọn nhiều)
   - **Include All option**: ✅

4. Sử dụng trong queries:
   ```promql
   {namespace="$namespace", pod=~"airflow.*"}
   ```

### Tạo Variable cho Pod

1. **Name**: `pod`
2. **Type**: **Query**
3. **Query**: `label_values(container_cpu_usage_seconds_total{namespace="$namespace"}, pod)`
4. **Depends on**: `namespace`

---

## Tips và Tricks

### 1. Refresh Dashboard
- Click icon **Refresh** (mũi tên tròn) để refresh data
- Hoặc chọn auto-refresh: **5s**, **10s**, **30s**, etc.

### 2. Time Range
- Click vào time range ở góc trên bên phải
- Chọn: **Last 5 minutes**, **Last 1 hour**, **Last 6 hours**, etc.
- Hoặc chọn **Custom range**

### 3. Panel Options
- **Legend**: Hiển thị/ẩn legend
- **Tooltip**: Cấu hình tooltip khi hover
- **Thresholds**: Thêm thresholds (ví dụ: warning > 80%, critical > 90%)

### 4. Dashboard Links
- Tạo links giữa các dashboards
- Vào **Dashboard settings** → **Links** → **Add link**

### 5. Annotations
- Thêm annotations để đánh dấu events
- Click **Annotations** ở menu bên trái

---

## Import Dashboard từ JSON

### Cách 1: Import từ Grafana.com
1. Vào **Dashboards** → **Import**
2. Nhập Dashboard ID từ [grafana.com/dashboards](https://grafana.com/dashboards)
3. Click **Load**
4. Chọn data source và **Import**

### Cách 2: Import từ JSON file
1. Vào **Dashboards** → **Import**
2. Click **Upload JSON file**
3. Chọn file JSON
4. Click **Import**

---

## Dashboard Templates có sẵn

### Kubernetes Dashboards
- **Kubernetes / Compute Resources / Cluster** - ID: 15758
- **Kubernetes / Compute Resources / Namespace** - ID: 15759
- **Kubernetes / Compute Resources / Pod** - ID: 15760
- **Kubernetes / Networking / Cluster** - ID: 15761

### Import từ Grafana.com
1. Vào **Dashboards** → **Import**
2. Nhập ID: `15758` (hoặc ID khác)
3. Click **Load**
4. Chọn Prometheus data source
5. Click **Import**

---

## Troubleshooting

### Dashboard không hiển thị data?

1. **Kiểm tra time range**: Có thể time range quá ngắn
2. **Kiểm tra query**: Query có đúng không
3. **Kiểm tra data source**: Đảm bảo chọn đúng Prometheus
4. **Kiểm tra labels**: Labels có khớp với pods/services không

### Panel hiển thị "No data"?

1. Kiểm tra query có trả về data không (dùng Explore)
2. Kiểm tra time range
3. Kiểm tra labels/filters
4. Thử query đơn giản hơn: `up{namespace="crypto-infra"}`

---

## Quick Start

1. **Xem dashboard có sẵn:**
   - Vào **Dashboards** → **Browse**
   - Click **Kubernetes / Compute Resources / Namespace (Pods)**
   - Chọn namespace: `crypto-infra`

2. **Tạo dashboard đơn giản:**
   - **Dashboards** → **New** → **New Dashboard**
   - **Add visualization**
   - Query: `{namespace="crypto-infra"}`
   - **Save**

3. **Import dashboard mẫu:**
   - **Dashboards** → **Import**
   - ID: `15758` (Kubernetes Cluster)
   - **Import**

