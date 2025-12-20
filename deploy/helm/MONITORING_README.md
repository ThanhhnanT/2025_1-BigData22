# Hướng dẫn Triển khai và Sử dụng Prometheus & Grafana Monitoring

## Tổng quan

Hệ thống monitoring sử dụng `kube-prometheus-stack` để giám sát toàn bộ hệ thống CRYPTO trên minikube, bao gồm:

- **Prometheus**: Thu thập và lưu trữ metrics
- **Grafana**: Dashboard và visualization
- **Alertmanager**: Quản lý alerts (tùy chọn)
- **ServiceMonitors**: Tự động phát hiện và scrape metrics từ các services

## Kiến trúc

```
┌─────────────────────────────────────────────────────────┐
│           crypto-monitoring namespace                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │  Prometheus  │  │   Grafana     │  │ Alertmanager  │ │
│  └──────┬───────┘  └──────┬───────┘  └───────────────┘ │
│         │                 │                             │
│         └─────────────────┴─────────────────────────────┘
│                    │
│         ┌──────────┴──────────┐
│         │  ServiceMonitors     │
│         └──────────┬───────────┘
│                    │
└────────────────────┼─────────────────────────────────────┘
                     │
         ┌───────────┼───────────┐
         │           │           │
    ┌────▼────┐ ┌───▼────┐ ┌───▼────┐
    │  Kafka  │ │ Spark  │ │Airflow │
    │        │ │        │ │ │        │
    └─────────┘ └───────┘ └────────┘
```

## Triển khai

### Bước 1: Triển khai Monitoring Stack

```bash
cd deploy/helm
./deploy-monitoring.sh
```

Script này sẽ:
- Kiểm tra minikube đang chạy
- Tạo namespace `crypto-monitoring`
- Thêm Helm repository `prometheus-community`
- Cài đặt `kube-prometheus-stack` với cấu hình từ `values-minikube.yaml`
- Hiển thị thông tin truy cập

### Bước 2: Áp dụng ServiceMonitors

Sau khi monitoring stack đã được triển khai, áp dụng các ServiceMonitor resources:

```bash
cd deploy/k8s_web
./apply-servicemonitors.sh
```

Script này sẽ tạo ServiceMonitors cho:
- Backend FastAPI (nếu service tồn tại)
- Kafka cluster (Strimzi)
- Spark Operator
- Airflow StatsD

## Truy cập

### Grafana

**Cách 1: NodePort (Khuyến nghị cho minikube)**
```bash
minikube service crypto-monitoring-grafana -n crypto-monitoring
```

**Cách 2: Port Forward**
```bash
kubectl port-forward svc/crypto-monitoring-grafana 3000:80 -n crypto-monitoring
```
Sau đó mở: http://localhost:3000

**Credentials mặc định:**
- Username: `admin`
- Password: Lấy bằng lệnh:
  ```bash
  kubectl get secret crypto-monitoring-grafana -n crypto-monitoring -o jsonpath="{.data.admin-password}" | base64 -d
  ```

### Prometheus

```bash
kubectl port-forward svc/crypto-monitoring-kube-prometheus-prometheus 9090:9090 -n crypto-monitoring
```
Sau đó mở: http://localhost:9090

### Script tiện ích

Sử dụng script `access-monitoring.sh` để xem thông tin truy cập:

```bash
cd deploy/helm
./access-monitoring.sh
```

## Cấu hình

### File cấu hình chính

File cấu hình monitoring nằm tại: `deploy/helm/values-minikube.yaml`

Các cấu hình quan trọng:

```yaml
monitoring:
  enabled: true
  releaseName: crypto-monitoring
  namespace: crypto-monitoring
  chart:
    repo: prometheus-community/kube-prometheus-stack
  values:
    grafana:
      service:
        type: NodePort
        nodePort: 32000
    prometheus:
      service:
        type: ClusterIP
      prometheusSpec:
        serviceMonitorSelectorNilUsesHelmValues: false
        serviceMonitorSelector: {}
        serviceMonitorNamespaceSelector: {}
```

### ServiceMonitors

Các ServiceMonitor resources được đặt trong `deploy/k8s_web/`:

- `backend-servicemonitor.yaml`: Backend FastAPI metrics
- `kafka-servicemonitor.yaml`: Kafka cluster metrics
- `spark-operator-servicemonitor.yaml`: Spark Operator metrics
- `airflow-statsd-servicemonitor.yaml`: Airflow StatsD metrics

## Kiểm tra và Troubleshooting

### Kiểm tra trạng thái pods

```bash
kubectl get pods -n crypto-monitoring
```

Tất cả pods phải ở trạng thái `Running`.

### Kiểm tra Services

```bash
kubectl get svc -n crypto-monitoring
```

### Kiểm tra ServiceMonitors

```bash
kubectl get servicemonitors -A
```

### Kiểm tra Prometheus Targets

1. Port-forward Prometheus:
   ```bash
   kubectl port-forward svc/crypto-monitoring-kube-prometheus-prometheus 9090:9090 -n crypto-monitoring
   ```

2. Mở http://localhost:9090/targets

3. Kiểm tra các targets có status `UP` không

### Xem logs

**Grafana logs:**
```bash
kubectl logs -l app.kubernetes.io/name=grafana -n crypto-monitoring
```

**Prometheus logs:**
```bash
kubectl logs -l app.kubernetes.io/name=prometheus -n crypto-monitoring
```

### Vấn đề thường gặp

1. **ServiceMonitor không được phát hiện:**
   - Kiểm tra labels trong ServiceMonitor có khớp với labels trong Service không
   - Kiểm tra `serviceMonitorSelector` trong Prometheus config
   - Đảm bảo ServiceMonitor có label `release: crypto-monitoring`

2. **Metrics endpoint không hoạt động:**
   - Kiểm tra service có expose metrics endpoint không (thường là `/metrics`)
   - Kiểm tra port name trong ServiceMonitor có đúng không
   - Kiểm tra service có đang chạy không

3. **Grafana không truy cập được:**
   - Kiểm tra NodePort có được assign chưa: `kubectl get svc -n crypto-monitoring`
   - Thử dùng port-forward thay vì NodePort
   - Kiểm tra minikube service có hoạt động không

## Tích hợp với Backend FastAPI

Để Backend FastAPI expose metrics cho Prometheus, bạn cần:

1. **Cài đặt Prometheus client library:**
   ```bash
   pip install prometheus-fastapi-instrumentator
   ```

2. **Thêm vào `backend_fastapi/app/main.py`:**
   ```python
   from prometheus_fastapi_instrumentator import Instrumentator
   
   # Thêm sau khi tạo app
   Instrumentator().instrument(app).expose(app)
   ```

3. **Rebuild và redeploy backend image**

4. **Áp dụng ServiceMonitor:**
   ```bash
   kubectl apply -f deploy/k8s_web/backend-servicemonitor.yaml
   ```

## Tích hợp với Kafka (Strimzi)

Strimzi Kafka tự động expose metrics qua JMX Prometheus Exporter. Để bật:

1. **Cập nhật `Kafka/kafka-helm.yaml` để thêm metrics config:**
   ```yaml
   spec:
     kafka:
       metricsConfig:
         type: jmxPrometheusExporter
         valueFrom:
           configMapKeyRef:
             name: kafka-metrics
             key: kafka-metrics-config.yml
   ```

2. **Tạo ConfigMap với JMX exporter config**

3. **Áp dụng ServiceMonitor:**
   ```bash
   kubectl apply -f deploy/k8s_web/kafka-servicemonitor.yaml
   ```

## Dashboard mẫu

Sau khi đăng nhập Grafana, bạn có thể:

1. **Import pre-built dashboards:**
   - Kubernetes Cluster Monitoring
   - Kafka Exporter
   - Node Exporter

2. **Tạo custom dashboards:**
   - Query metrics từ Prometheus
   - Tạo visualizations

## Nâng cấp

Để nâng cấp monitoring stack:

```bash
cd deploy/helm
helm upgrade crypto-monitoring prometheus-community/kube-prometheus-stack \
  --namespace crypto-monitoring \
  --values values-minikube.yaml
```

## Gỡ cài đặt

```bash
helm uninstall crypto-monitoring -n crypto-monitoring
kubectl delete namespace crypto-monitoring
```

## Tài liệu tham khảo

- [kube-prometheus-stack Chart](https://github.com/prometheus-community/helm-charts/tree/main/charts/kube-prometheus-stack)
- [Prometheus Operator](https://github.com/prometheus-operator/prometheus-operator)
- [Grafana Documentation](https://grafana.com/docs/)


